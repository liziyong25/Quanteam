#!/usr/bin/env python3
"""
zsxq_xlsx_downloader.py

合法前提：
- 仅在用户已合法加入并已登录知识星球（zsxq）的情况下使用；
- 程序只使用用户自行从浏览器 Network 抓包获得的登录态（Authorization 或 Cookie）；
- 不包含任何绕过权限/风控、破解验证码、未授权访问的行为。

功能：
- 自动翻页遍历指定 group 的 topics；
- 扫描 topic 内多路径附件 files；
- 只下载指定扩展名（默认 .xlsx）的附件；
- 通过 /v2/files/{file_id}/download_url 获取短时有效真实下载链接后再下载；
- 断点续跑（--resume）：保存已成功下载的 file_id，避免重复下载；
- 生成 manifest（JSON Lines）记录每个附件处理结果。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple

try:
    import requests
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: requests. Install it first, e.g.:\n"
        "  pip install requests\n"
    ) from exc

try:
    from dateutil import parser as dateutil_parser
except ModuleNotFoundError:  # pragma: no cover
    dateutil_parser = None


API_BASE = "https://api.zsxq.com/v2"
WX_ORIGIN = "https://wx.zsxq.com"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)

MAX_COUNT = 50
DEFAULT_COUNT = 20

DEFAULT_SLEEP_TOPICS = 0.3
DEFAULT_SLEEP_DOWNLOAD_URL = 1.2

DEFAULT_CONNECT_TIMEOUT_S = 10.0
DEFAULT_READ_TIMEOUT_S = 30.0
DEFAULT_DOWNLOAD_READ_TIMEOUT_S = 300.0

DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_BASE_S = 1.0
DEFAULT_BACKOFF_CAP_S = 30.0

RESUME_STATE_FILENAME = "resume_state.json"
MANIFEST_FILENAME = "manifest.jsonl"
DOTENV_FILENAME = ".env"
DEFAULT_OUT_DIR_WINDOWS = r"D:\zxxq_xlsx"

# Windows reserved filenames (case-insensitive), without extension.
WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

# Invalid filename characters for Windows/macOS, plus ASCII control chars.
# NOTE: Must NOT accidentally match letters like "x" (e.g. ".xlsx").
_INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_ZSXQ_TZ_BASIC_RE = re.compile(r"([+-])(\d{2})(\d{2})$")
_FILE_ID_PREFIX_RE = re.compile(r"^(\d+)_")
_DK_DATE_8_RE = re.compile(r"(20\d{2}[01]\d[0-3]\d)$")
_DK_DATE_SEP_RE = re.compile(r"(20\d{2})[-_.](\d{2})[-_.](\d{2})$")


class FatalHTTPError(RuntimeError):
    pass


@dataclass
class Counters:
    pages: int = 0
    topics_fetched: int = 0
    topics_in_range: int = 0
    xlsx_found: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0


def _local_tz() -> tzinfo:
    return datetime.now().astimezone().tzinfo or timezone.utc


def _coerce_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_local_tz())
    return dt


def parse_zsxq_time(ts: str) -> datetime:
    """
    Parse zsxq time like: 2018-01-10T11:49:39.668+0800 (tz offset without colon).
    Returns timezone-aware datetime.
    """
    ts = ts.strip()
    if not ts:
        raise ValueError("empty time string")

    if dateutil_parser is not None:
        dt = dateutil_parser.parse(ts)
        return _coerce_aware(dt)

    # Fallback: normalize +0800 -> +08:00 for datetime.fromisoformat
    m = _ZSXQ_TZ_BASIC_RE.search(ts)
    if m:
        ts = ts[: m.start()] + f"{m.group(1)}{m.group(2)}:{m.group(3)}"
    dt = datetime.fromisoformat(ts)
    return _coerce_aware(dt)


def format_zsxq_time(dt: datetime) -> str:
    """
    Format datetime to zsxq style: YYYY-MM-DDTHH:MM:SS.mmm+0800 (no colon in tz).
    """
    dt = _coerce_aware(dt)
    ms = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}" + dt.strftime("%z")


def parse_user_time(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None

    # Try zsxq format first.
    try:
        return parse_zsxq_time(s)
    except Exception:
        pass

    if dateutil_parser is not None:
        dt = dateutil_parser.parse(s)
        return _coerce_aware(dt)

    # Fallback: datetime.fromisoformat (requires colon in tz if any).
    dt = datetime.fromisoformat(s)
    return _coerce_aware(dt)


def parse_exts(raw: str) -> Set[str]:
    items: List[str] = []
    for part in raw.split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part.startswith("."):
            part = part[1:]
        items.append(part)
    if not items:
        raise ValueError("--ext is empty")
    return set(items)


def is_ext_allowed(filename: str, allowed_exts: Set[str]) -> bool:
    filename = (filename or "").strip()
    if not filename:
        return False
    dot = filename.rfind(".")
    if dot <= 0 or dot == len(filename) - 1:
        return False
    ext = filename[dot + 1 :].lower()
    return ext in allowed_exts


def sanitize_filename(name: str, *, max_length: int = 180) -> str:
    name = (name or "").strip()
    if not name:
        return "file"

    name = _INVALID_FILENAME_CHARS_RE.sub("_", name)
    name = name.replace("\u200b", "")  # zero-width space
    name = name.strip().rstrip(". ")  # Windows forbids trailing dot/space
    if not name:
        return "file"

    # Avoid reserved device names on Windows.
    stem, suffix = os.path.splitext(name)
    if stem.lower() in WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"
        name = stem + suffix

    # Limit length while preserving extension.
    if len(name) > max_length:
        ext = suffix
        keep = max_length - len(ext)
        if keep <= 0:
            name = name[:max_length]
        else:
            name = stem[:keep] + ext
    return name


def _sleep(seconds: float) -> None:
    if seconds <= 0:
        return
    time.sleep(seconds)


def _jitter(max_jitter_s: float = 0.25) -> float:
    return random.random() * max_jitter_s


def _read_text_snippet(resp: requests.Response, limit: int = 500) -> str:
    try:
        text = resp.text
    except Exception:
        return ""
    text = text.replace("\r\n", "\n")
    return text[:limit]


def normalize_cookie_header(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty cookie")
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    # If user only pastes the token value, auto-wrap as zsxq_access_token=<token>.
    if "=" not in raw:
        raw = f"zsxq_access_token={raw}"
    return raw


def _guess_repo_root() -> Optional[Path]:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return None


def _find_dotenv_path(explicit_path: Optional[str]) -> Optional[Path]:
    if explicit_path:
        p = Path(explicit_path).expanduser()
        return p

    candidates: List[Path] = [Path.cwd() / DOTENV_FILENAME]
    repo_root = _guess_repo_root()
    if repo_root is not None:
        candidates.append(repo_root / DOTENV_FILENAME)
    candidates.append(Path(__file__).resolve().parent / DOTENV_FILENAME)
    for p in candidates:
        if p.is_file():
            return p
    return None


def _unquote_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_dotenv_file(path: Path, *, override: bool = False) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        # Strip inline comments for unquoted values.
        if value and value[0] not in ("'", '"'):
            value = value.split("#", 1)[0].rstrip()
        value = _unquote_env_value(value)
        env[key] = value

    for k, v in env.items():
        if override or k not in os.environ:
            os.environ[k] = v
    return env


def load_dotenv(explicit_path: Optional[str] = None) -> Optional[Path]:
    path = _find_dotenv_path(explicit_path)
    if path is None:
        return None
    if not path.is_file():
        raise FileNotFoundError(str(path))
    load_dotenv_file(path, override=False)
    return path


def _env_get(key: str) -> Optional[str]:
    v = os.environ.get(key)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _env_int(key: str) -> Optional[int]:
    v = _env_get(key)
    if v is None:
        return None
    return int(v)


def _env_float(key: str) -> Optional[float]:
    v = _env_get(key)
    if v is None:
        return None
    return float(v)


def _env_bool(key: str) -> Optional[bool]:
    v = _env_get(key)
    if v is None:
        return None
    s = v.strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    raise ValueError(f"{key} must be a boolean (1/0/true/false/yes/no), got: {v!r}")


def _request_json_with_retries(
    session: requests.Session,
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: Tuple[float, float] = (DEFAULT_CONNECT_TIMEOUT_S, DEFAULT_READ_TIMEOUT_S),
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
    backoff_cap_s: float = DEFAULT_BACKOFF_CAP_S,
) -> Dict[str, Any]:
    last_exc: Optional[BaseException] = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.request(method, url, params=params, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            delay = min(backoff_cap_s, backoff_base_s * (2 ** (attempt - 1))) + _jitter()
            print(f"[retry] network_error attempt={attempt}/{max_retries} sleep={delay:.2f}s error={exc}")
            _sleep(delay)
            continue

        if resp.status_code in (401, 403):
            snippet = _read_text_snippet(resp)
            raise FatalHTTPError(
                f"HTTP {resp.status_code} for {url}. "
                "可能是 Authorization/Cookie 失效 / 未加入星球 / 触发风控。"
                f" response_snippet={snippet!r}"
            )

        if resp.status_code == 429 or 500 <= resp.status_code <= 599:
            retry_after = resp.headers.get("Retry-After")
            delay = min(backoff_cap_s, backoff_base_s * (2 ** (attempt - 1)))
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    pass
            delay = delay + _jitter()
            if resp.status_code == 429 and attempt == 1:
                print(
                    "[risk-control] HTTP 429 Too Many Requests. "
                    "将使用指数退避重试；如仍频繁触发，建议加大 --sleep-download-url/--sleep-topics。"
                )
            print(
                f"[retry] http_status={resp.status_code} attempt={attempt}/{max_retries} "
                f"sleep={delay:.2f}s url={url}"
            )
            _sleep(delay)
            continue

        if resp.status_code < 200 or resp.status_code >= 300:
            snippet = _read_text_snippet(resp)
            raise RuntimeError(f"HTTP {resp.status_code} for {url} response_snippet={snippet!r}")

        try:
            data = resp.json()
        except Exception as exc:
            snippet = _read_text_snippet(resp)
            raise RuntimeError(f"Invalid JSON for {url} error={exc} response_snippet={snippet!r}") from exc

        succeeded = data.get("succeeded")
        if succeeded is False:
            code = data.get("code")
            msg = data.get("msg") or data.get("message") or data.get("error") or ""
            code_int: Optional[int] = None
            if isinstance(code, int):
                code_int = code
            elif isinstance(code, str) and code.isdigit():
                code_int = int(code)

            if code_int in (401, 403):
                raise FatalHTTPError(
                    f"API denied for {url} code={code_int} msg={msg!r}. "
                    "可能是 Authorization/Cookie 失效 / 未加入星球 / 触发风控。"
                )

            if attempt < max_retries:
                delay = min(backoff_cap_s, backoff_base_s * (2 ** (attempt - 1))) + _jitter()
                print(
                    f"[retry] api_error succeeded=false code={code!r} attempt={attempt}/{max_retries} "
                    f"sleep={delay:.2f}s url={url} msg={msg!r}"
                )
                _sleep(delay)
                continue
            raise RuntimeError(
                f"API error succeeded=false code={code!r} url={url} msg={msg!r}"
            )
        return data

    raise RuntimeError(f"Request failed after {max_retries} retries for {url} last_error={last_exc}")


def _iter_file_objs(obj: Any) -> Iterator[Dict[str, Any]]:
    """
    Recursively scan any dict/list, yielding dict items from "files": [ {...}, ... ].
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "files" and isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        yield item
                continue
            yield from _iter_file_objs(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _iter_file_objs(it)


def extract_file_entries(topic: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Multi-path scan for attachments under common containers, plus a safe recursive fallback.
    """
    results: List[Dict[str, Any]] = []

    # Known common containers first (more predictable).
    for key in ("talk", "question", "answer", "task", "solution"):
        container = topic.get(key)
        if container is None:
            continue
        results.extend(list(_iter_file_objs(container)))

    # Fallback: scan whole topic (covers other shapes like "comments" etc.).
    results.extend(list(_iter_file_objs(topic)))

    # Keep only file-like dicts.
    filtered: List[Dict[str, Any]] = []
    for f in results:
        if not isinstance(f, dict):
            continue
        if "file_id" in f or "id" in f:
            filtered.append(f)
    return filtered


def _file_id_of(file_obj: Dict[str, Any]) -> Optional[str]:
    fid = file_obj.get("file_id", None)
    if fid is None:
        fid = file_obj.get("id", None)
    if fid is None:
        return None
    return str(fid)


def _file_name_of(file_obj: Dict[str, Any]) -> str:
    return (
        str(file_obj.get("name") or file_obj.get("filename") or file_obj.get("original_name") or "")
    )


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_resume_state(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    ids = data.get("downloaded_file_ids", [])
    if not isinstance(ids, list):
        return set()
    return {str(x) for x in ids if x is not None}


def normalize_name_for_match(name: str) -> str:
    # Normalize to the on-disk filename shape (after sanitization), then compare case-insensitively.
    return sanitize_filename(name).lower()


def strip_file_id_prefix(filename: str) -> Tuple[Optional[str], str]:
    """
    If filename is like "<file_id>_rest.ext", return (file_id, "rest.ext").
    Otherwise return (None, original filename).
    """
    m = _FILE_ID_PREFIX_RE.match(filename)
    if not m:
        return None, filename
    fid = m.group(1)
    rest = filename[m.end() :]
    if not rest:
        return fid, filename
    return fid, rest


def extract_dk_fuzzy_key(filename: str) -> Optional[str]:
    """
    For "奇衡DK" Excel files, build a fuzzy match key based on (category prefix, date).

    User-provided naming convention examples:
    - 【V】奇衡DK....20251119.xlsx
    - 奇衡DK星....20251119.xlsx
    - 【V】奇衡DK全球....20251119.xlsx

    Returns:
        "dk:YYYYMMDD" / "dk_star:YYYYMMDD" / "dk_global:YYYYMMDD", or None if not matchable.
    """
    raw = (filename or "").strip()
    if not raw:
        return None

    _, raw = strip_file_id_prefix(raw)
    base = os.path.basename(raw)
    stem, _ = os.path.splitext(base)
    stem_no_space = re.sub(r"\s+", "", stem)
    lower = stem_no_space.lower()

    category: Optional[str] = None
    # Order matters: more specific prefixes first.
    if lower.startswith("【v】奇衡dk全球") or lower.startswith("奇衡dk全球"):
        category = "dk_global"
    elif lower.startswith("奇衡dk星"):
        category = "dk_star"
    elif lower.startswith("【v】奇衡dk") or lower.startswith("奇衡dk"):
        category = "dk"
    else:
        return None

    date_str: Optional[str] = None
    m = _DK_DATE_8_RE.search(stem_no_space)
    if m:
        date_str = m.group(1)
    else:
        m2 = _DK_DATE_SEP_RE.search(stem_no_space)
        if m2:
            date_str = f"{m2.group(1)}{m2.group(2)}{m2.group(3)}"
    if not date_str:
        return None
    return f"{category}:{date_str}"


def scan_local_file_index(
    out_dir: Path,
    *,
    allowed_exts: Set[str],
    strip_existing_id_prefix: bool,
) -> Tuple[Dict[str, Path], Dict[str, Path], Dict[str, Path], int]:
    """
    Build local indexes:
    - by_file_id: {file_id: path} for files named like "<file_id>_anything"
    - by_name: {normalized_filename: path} for all files (manual downloads included)
    - by_dk_key: {"dk_global:YYYYMMDD": path, ...} for fuzzy match by (prefix, date)
    """
    by_file_id: Dict[str, Path] = {}
    by_name: Dict[str, Path] = {}
    by_dk_key: Dict[str, Path] = {}
    renamed_count = 0
    if not out_dir.exists():
        return by_file_id, by_name, by_dk_key, renamed_count
    for p in out_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix == ".part":
            # Ignore incomplete temp files.
            continue
        if p.name in (MANIFEST_FILENAME, RESUME_STATE_FILENAME):
            continue

        # If we previously saved as "<file_id>_name.xlsx", optionally normalize it to "name.xlsx"
        # for easier local searching (avoid file_id prefix interfering with name/date matching).
        fid, stripped_name = strip_file_id_prefix(p.name)
        if (
            strip_existing_id_prefix
            and fid
            and stripped_name != p.name
            and is_ext_allowed(stripped_name, allowed_exts)
        ):
            target = p.with_name(stripped_name)
            if target != p and not target.exists():
                try:
                    os.replace(p, target)
                    p = target
                    renamed_count += 1
                except OSError:
                    # Non-fatal: keep original name if rename fails.
                    pass

        by_name.setdefault(normalize_name_for_match(p.name), p)
        # Also index "stripped name" if this file has a file_id prefix (even if we didn't rename).
        if fid and stripped_name:
            by_file_id.setdefault(fid, p)
            by_name.setdefault(normalize_name_for_match(stripped_name), p)

        # Fuzzy match keys (DK prefix + date).
        key1 = extract_dk_fuzzy_key(p.name)
        if key1:
            by_dk_key.setdefault(key1, p)
        if fid and stripped_name:
            key2 = extract_dk_fuzzy_key(stripped_name)
            if key2:
                by_dk_key.setdefault(key2, p)

    return by_file_id, by_name, by_dk_key, renamed_count


def _save_resume_state(path: Path, downloaded_ids: Set[str]) -> None:
    tmp = path.with_suffix(".tmp")
    payload = {
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        "downloaded_file_ids": sorted(downloaded_ids),
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _append_manifest(manifest_path: Path, record: Dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False)
    with manifest_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _topic_id(topic: Dict[str, Any]) -> str:
    return str(topic.get("topic_id") or topic.get("id") or "")


def _topic_create_time(topic: Dict[str, Any]) -> str:
    return str(topic.get("create_time") or "")


def _fetch_topics_page(
    session: requests.Session,
    group_id: str,
    *,
    scope: str,
    count: int,
    end_time: Optional[str],
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/groups/{group_id}/topics"
    params: Dict[str, Any] = {"scope": scope, "count": count}
    if end_time:
        params["end_time"] = end_time
    data = _request_json_with_retries(session, "GET", url, params=params)
    resp_data = data.get("resp_data") or {}
    topics = resp_data.get("topics") or []
    if not isinstance(topics, list):
        raise RuntimeError("Unexpected topics payload")
    return [t for t in topics if isinstance(t, dict)]


def _get_download_url(session: requests.Session, file_id: str, *, max_attempts: int = 3) -> str:
    """
    Some cases may return HTTP 200 but no download_url (or succeeded=false). Retry a few times with backoff.
    """
    url = f"{API_BASE}/files/{file_id}/download_url"
    last_info: Optional[Dict[str, Any]] = None

    for attempt in range(1, max_attempts + 1):
        data = _request_json_with_retries(session, "GET", url)
        resp_data = data.get("resp_data") or {}
        dl = resp_data.get("download_url")
        if dl:
            return str(dl)

        succeeded = data.get("succeeded")
        code = data.get("code") or resp_data.get("code")
        msg = (
            data.get("msg")
            or data.get("message")
            or resp_data.get("msg")
            or resp_data.get("message")
            or resp_data.get("error")
        )
        last_info = {"succeeded": succeeded, "code": code, "msg": msg}

        code_int: Optional[int] = None
        if isinstance(code, int):
            code_int = code
        elif isinstance(code, str) and code.isdigit():
            code_int = int(code)
        if code_int in (401, 403):
            raise FatalHTTPError(
                f"download_url denied for file_id={file_id} code={code_int} msg={msg!r}"
            )

        if attempt < max_attempts:
            delay = min(10.0, DEFAULT_BACKOFF_BASE_S * (2 ** (attempt - 1))) + _jitter()
            print(
                f"[retry] download_url_missing attempt={attempt}/{max_attempts} "
                f"sleep={delay:.2f}s file_id={file_id} info={last_info}"
            )
            _sleep(delay)

    raise RuntimeError(f"download_url missing for file_id={file_id} last_info={last_info}")


def _download_stream_to_file(
    session: requests.Session,
    url: str,
    dest_path: Path,
    *,
    timeout: Tuple[float, float] = (DEFAULT_CONNECT_TIMEOUT_S, DEFAULT_DOWNLOAD_READ_TIMEOUT_S),
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
    backoff_cap_s: float = DEFAULT_BACKOFF_CAP_S,
) -> None:
    part_path = dest_path.with_suffix(dest_path.suffix + ".part")
    last_exc: Optional[BaseException] = None

    for attempt in range(1, max_retries + 1):
        try:
            with session.get(url, stream=True, timeout=timeout, allow_redirects=True) as resp:
                if resp.status_code in (401, 403):
                    raise FatalHTTPError(
                        f"Download HTTP {resp.status_code}. 可能是签名过期/风控/权限不足。"
                    )
                if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                    delay = min(backoff_cap_s, backoff_base_s * (2 ** (attempt - 1))) + _jitter()
                    print(
                        f"[retry] download_status={resp.status_code} attempt={attempt}/{max_retries} "
                        f"sleep={delay:.2f}s"
                    )
                    _sleep(delay)
                    continue
                if resp.status_code < 200 or resp.status_code >= 300:
                    raise RuntimeError(
                        f"Download HTTP {resp.status_code} response_snippet={_read_text_snippet(resp)!r}"
                    )

                _ensure_dir(dest_path.parent)
                with part_path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        if not chunk:
                            continue
                        f.write(chunk)
                os.replace(part_path, dest_path)
                return
        except FatalHTTPError:
            # Fail fast to avoid repeated potentially blocked downloads.
            raise
        except (requests.Timeout, requests.ConnectionError, RuntimeError) as exc:
            last_exc = exc
            try:
                if part_path.exists():
                    part_path.unlink()
            except Exception:
                pass
            delay = min(backoff_cap_s, backoff_base_s * (2 ** (attempt - 1))) + _jitter()
            print(f"[retry] download_error attempt={attempt}/{max_retries} sleep={delay:.2f}s error={exc}")
            _sleep(delay)
            continue

    raise RuntimeError(f"Download failed after {max_retries} retries last_error={last_exc}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zsxq_xlsx_downloader",
        description=(
            "Download Excel attachments from zsxq group topics using your own login state "
            "(Authorization or Cookie)."
        ),
    )
    p.add_argument(
        "--env-file",
        default=argparse.SUPPRESS,
        help=f"load env vars from this file (default: auto-detect {DOTENV_FILENAME})",
    )
    p.add_argument(
        "--group-id",
        default=argparse.SUPPRESS,
        help="zsxq group id, e.g. 15552882181122 (or env ZSXQ_GROUP_ID)",
    )
    p.add_argument(
        "--out-dir",
        default=argparse.SUPPRESS,
        help=(
            "output directory (default: D:\\zxxq_xlsx on Windows, ./zsxq_xlsx otherwise; "
            "or env ZSXQ_OUT_DIR)"
        ),
    )
    p.add_argument(
        "--scope",
        default=argparse.SUPPRESS,
        help="topics scope (default: all; e.g. with_files; or env ZSXQ_SCOPE)",
    )
    p.add_argument(
        "--count",
        type=int,
        default=argparse.SUPPRESS,
        help=f"page size 1-{MAX_COUNT} (default: {DEFAULT_COUNT}; or env ZSXQ_COUNT)",
    )
    p.add_argument(
        "--auth",
        default=argparse.SUPPRESS,
        help="Authorization header value (or env ZSXQ_AUTH)",
    )
    p.add_argument(
        "--cookie",
        default=argparse.SUPPRESS,
        help="Cookie header value, e.g. zsxq_access_token=... (or env ZSXQ_COOKIE)",
    )
    p.add_argument(
        "--keep-id-prefix",
        action="store_true",
        default=argparse.SUPPRESS,
        help=(
            "keep filenames as '<file_id>_name.xlsx' (default: save as original name; "
            "or env ZSXQ_KEEP_ID_PREFIX=1)"
        ),
    )
    p.add_argument(
        "--sleep-topics",
        type=float,
        default=argparse.SUPPRESS,
        help=f"sleep between topics pages (default: {DEFAULT_SLEEP_TOPICS}; or env ZSXQ_SLEEP_TOPICS)",
    )
    p.add_argument(
        "--sleep-download-url",
        type=float,
        default=argparse.SUPPRESS,
        help=(
            f"sleep between /download_url calls (default: {DEFAULT_SLEEP_DOWNLOAD_URL}; "
            "or env ZSXQ_SLEEP_DOWNLOAD_URL)"
        ),
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=argparse.SUPPRESS,
        help="debug only: stop after N pages (or env ZSXQ_MAX_PAGES)",
    )
    p.add_argument(
        "--max-downloads",
        type=int,
        default=argparse.SUPPRESS,
        help="stop after N successful downloads (or env ZSXQ_MAX_DOWNLOADS)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="only list xlsx, do not download (or env ZSXQ_DRY_RUN=1)",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        default=argparse.SUPPRESS,
        help=f"resume mode (or env ZSXQ_RESUME=1): persist downloaded file_ids to {RESUME_STATE_FILENAME}",
    )
    p.add_argument(
        "--since",
        default=argparse.SUPPRESS,
        help="filter topics by create_time >= since (zsxq time or ISO datetime) (or env ZSXQ_SINCE)",
    )
    p.add_argument(
        "--until",
        default=argparse.SUPPRESS,
        help="filter topics by create_time <= until (zsxq time or ISO datetime) (or env ZSXQ_UNTIL)",
    )
    p.add_argument(
        "--ext",
        default=argparse.SUPPRESS,
        help="comma-separated extensions to download, e.g. xlsx,xlsm (default: xlsx; or env ZSXQ_EXT)",
    )
    return p


def _print_progress(c: Counters) -> None:
    print(
        "progress "
        + " ".join(
            [
                f"pages={c.pages}",
                f"topics={c.topics_fetched}",
                f"xlsx_found={c.xlsx_found}",
                f"downloaded={c.downloaded}",
                f"skipped={c.skipped}",
                f"failed={c.failed}",
            ]
        )
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    env_file = getattr(args, "env_file", None) or _env_get("ZSXQ_ENV_FILE")
    try:
        loaded_dotenv = load_dotenv(env_file)
    except FileNotFoundError:
        print(f"Env file not found: {env_file!r}")
        return 2
    except Exception as exc:
        print(f"Failed to load env file: {exc}")
        return 2
    if loaded_dotenv is not None:
        print(f"[dotenv] loaded {loaded_dotenv}")

    group_id = getattr(args, "group_id", None) or _env_get("ZSXQ_GROUP_ID")
    if not group_id:
        print("Missing group id: provide --group-id or set env ZSXQ_GROUP_ID (via .env).")
        return 2

    default_out_dir = DEFAULT_OUT_DIR_WINDOWS if os.name == "nt" else "./zsxq_xlsx"
    out_dir_str = getattr(args, "out_dir", None) or _env_get("ZSXQ_OUT_DIR") or default_out_dir
    scope = getattr(args, "scope", None) or _env_get("ZSXQ_SCOPE") or "all"

    count = getattr(args, "count", None)
    if count is None:
        try:
            count = _env_int("ZSXQ_COUNT") or DEFAULT_COUNT
        except ValueError as exc:
            print(f"Invalid env ZSXQ_COUNT: {exc}")
            return 2

    sleep_topics = getattr(args, "sleep_topics", None)
    if sleep_topics is None:
        try:
            sleep_topics = _env_float("ZSXQ_SLEEP_TOPICS") or DEFAULT_SLEEP_TOPICS
        except ValueError as exc:
            print(f"Invalid env ZSXQ_SLEEP_TOPICS: {exc}")
            return 2

    sleep_download_url = getattr(args, "sleep_download_url", None)
    if sleep_download_url is None:
        try:
            sleep_download_url = _env_float("ZSXQ_SLEEP_DOWNLOAD_URL") or DEFAULT_SLEEP_DOWNLOAD_URL
        except ValueError as exc:
            print(f"Invalid env ZSXQ_SLEEP_DOWNLOAD_URL: {exc}")
            return 2

    max_pages = getattr(args, "max_pages", None)
    if max_pages is None:
        try:
            max_pages = _env_int("ZSXQ_MAX_PAGES")
        except ValueError as exc:
            print(f"Invalid env ZSXQ_MAX_PAGES: {exc}")
            return 2

    max_downloads = getattr(args, "max_downloads", None)
    if max_downloads is None:
        try:
            max_downloads = _env_int("ZSXQ_MAX_DOWNLOADS")
        except ValueError as exc:
            print(f"Invalid env ZSXQ_MAX_DOWNLOADS: {exc}")
            return 2

    dry_run = bool(getattr(args, "dry_run", False))
    if not dry_run:
        try:
            dry_run = bool(_env_bool("ZSXQ_DRY_RUN") or False)
        except ValueError as exc:
            print(str(exc))
            return 2

    resume = bool(getattr(args, "resume", False))
    if not resume:
        try:
            resume = bool(_env_bool("ZSXQ_RESUME") or False)
        except ValueError as exc:
            print(str(exc))
            return 2

    since_raw = getattr(args, "since", None) or _env_get("ZSXQ_SINCE")
    until_raw = getattr(args, "until", None) or _env_get("ZSXQ_UNTIL")
    since_dt = parse_user_time(since_raw)
    until_dt = parse_user_time(until_raw)
    if since_dt and until_dt and since_dt > until_dt:
        print("--since must be <= --until")
        return 2

    ext_raw = getattr(args, "ext", None) or _env_get("ZSXQ_EXT") or "xlsx"
    try:
        allowed_exts = parse_exts(ext_raw)
    except ValueError as exc:
        print(f"Invalid extensions: {exc}")
        return 2

    if not (1 <= count <= MAX_COUNT):
        print(f"--count must be 1-{MAX_COUNT}")
        return 2
    if max_pages is not None and max_pages <= 0:
        print("--max-pages must be > 0")
        return 2
    if max_downloads is not None and max_downloads <= 0:
        print("--max-downloads must be > 0")
        return 2
    if sleep_topics < 0 or sleep_download_url < 0:
        print("--sleep-topics/--sleep-download-url must be >= 0")
        return 2

    auth = getattr(args, "auth", None) or _env_get("ZSXQ_AUTH")
    cookie = getattr(args, "cookie", None) or _env_get("ZSXQ_COOKIE")
    if not auth and not cookie:
        print("Missing login state: provide --auth/ZSXQ_AUTH or --cookie/ZSXQ_COOKIE.")
        return 2

    keep_id_prefix = bool(getattr(args, "keep_id_prefix", False))
    if not keep_id_prefix:
        try:
            keep_id_prefix = bool(_env_bool("ZSXQ_KEEP_ID_PREFIX") or False)
        except ValueError as exc:
            print(str(exc))
            return 2
    strip_existing_id_prefix = not keep_id_prefix
    if strip_existing_id_prefix:
        try:
            strip_existing_id_prefix = bool(_env_bool("ZSXQ_STRIP_EXISTING_ID_PREFIX") or True)
        except ValueError as exc:
            print(str(exc))
            return 2

    cookie_header: Optional[str] = None
    if cookie:
        try:
            cookie_header = normalize_cookie_header(cookie)
        except ValueError as exc:
            print(f"Invalid cookie: {exc}")
            return 2

    out_dir = Path(out_dir_str)
    _ensure_dir(out_dir)
    manifest_path = out_dir / MANIFEST_FILENAME
    resume_path = out_dir / RESUME_STATE_FILENAME

    local_by_id, local_by_name, local_by_dk, renamed = scan_local_file_index(
        out_dir,
        allowed_exts=allowed_exts,
        strip_existing_id_prefix=(strip_existing_id_prefix and not dry_run),
    )
    print(
        f"local_files_by_id={len(local_by_id)} local_files_by_name={len(local_by_name)} "
        f"local_files_by_dk={len(local_by_dk)} renamed={renamed} out_dir={out_dir}"
    )

    downloaded_ids: Set[str] = set()
    if resume:
        downloaded_ids = _load_resume_state(resume_path)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": DEFAULT_UA,
            "Origin": WX_ORIGIN,
            "Referer": f"{WX_ORIGIN}/",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    if auth:
        session.headers["Authorization"] = auth
    if cookie_header:
        session.headers["Cookie"] = cookie_header

    counters = Counters()
    seen_file_ids: Set[str] = set()

    end_time: Optional[str] = format_zsxq_time(until_dt) if until_dt else None
    reached_since_boundary = False
    stop_due_to_max_downloads = False

    while True:
        if max_pages is not None and counters.pages >= max_pages:
            break
        if stop_due_to_max_downloads:
            break

        try:
            topics = _fetch_topics_page(session, str(group_id), scope=scope, count=count, end_time=end_time)
        except FatalHTTPError as exc:
            print(f"[fatal] {exc}")
            return 3
        except Exception as exc:
            print(f"[error] fetch_topics_failed error={exc}")
            return 1

        if not topics:
            break

        counters.pages += 1
        counters.topics_fetched += len(topics)

        for topic in topics:
            t_id = _topic_id(topic)
            t_ct_raw = _topic_create_time(topic)

            t_dt: Optional[datetime] = None
            if t_ct_raw:
                try:
                    t_dt = parse_zsxq_time(t_ct_raw)
                except Exception:
                    t_dt = None

            # Filter by until/since
            if until_dt and t_dt and t_dt > until_dt:
                continue
            if since_dt and t_dt and t_dt < since_dt:
                reached_since_boundary = True
                continue

            counters.topics_in_range += 1

            file_entries = extract_file_entries(topic)
            for file_obj in file_entries:
                fid = _file_id_of(file_obj)
                if not fid:
                    continue

                if fid in seen_file_ids:
                    continue
                seen_file_ids.add(fid)

                original_name = _file_name_of(file_obj)
                if not original_name:
                    # Best-effort default name.
                    original_name = f"{fid}.xlsx"

                if not is_ext_allowed(original_name, allowed_exts):
                    continue

                counters.xlsx_found += 1

                safe_name = sanitize_filename(original_name)
                if keep_id_prefix:
                    final_path = out_dir / f"{fid}_{safe_name}"
                else:
                    final_path = out_dir / safe_name
                dk_key = extract_dk_fuzzy_key(original_name)

                # Resume/skip checks
                existing_path = local_by_id.get(fid)
                skip_reason: Optional[str] = None
                if existing_path is not None and existing_path.exists():
                    skip_reason = "file_id_exists"
                if existing_path is None and final_path.exists():
                    existing_path = final_path
                    local_by_id[fid] = final_path
                    local_by_name.setdefault(normalize_name_for_match(final_path.name), final_path)
                    if dk_key:
                        local_by_dk.setdefault(dk_key, final_path)
                    skip_reason = "path_exists"

                if existing_path is None:
                    existing_by_name = local_by_name.get(normalize_name_for_match(original_name))
                    if existing_by_name is not None and existing_by_name.exists():
                        existing_path = existing_by_name
                        # Mark this file_id as present during this run to avoid duplicates.
                        local_by_id[fid] = existing_by_name
                        if dk_key:
                            local_by_dk.setdefault(dk_key, existing_by_name)
                        skip_reason = "name_exists"

                if existing_path is None and dk_key:
                    existing_by_dk = local_by_dk.get(dk_key)
                    if existing_by_dk is not None and existing_by_dk.exists():
                        existing_path = existing_by_dk
                        local_by_id[fid] = existing_by_dk
                        skip_reason = "dk_date_exists"

                if existing_path is not None and existing_path.exists():
                    counters.skipped += 1
                    if resume and fid not in downloaded_ids:
                        downloaded_ids.add(fid)
                        _save_resume_state(resume_path, downloaded_ids)
                    _append_manifest(
                        manifest_path,
                        {
                            "file_id": fid,
                            "original_name": original_name,
                            "topic_id": t_id,
                            "topic_create_time": t_ct_raw,
                            "downloaded_at": None,
                            "saved_path": str(existing_path),
                            "status": "skip",
                            "reason": skip_reason or "file_exists",
                        },
                    )
                    continue

                if dry_run:
                    print(f"[dry-run] file_id={fid} name={original_name!r} topic_id={t_id} time={t_ct_raw}")
                    counters.skipped += 1
                    _append_manifest(
                        manifest_path,
                        {
                            "file_id": fid,
                            "original_name": original_name,
                            "topic_id": t_id,
                            "topic_create_time": t_ct_raw,
                            "downloaded_at": None,
                            "saved_path": str(final_path),
                            "status": "dry_run",
                            "reason": None,
                        },
                    )
                    continue

                # Rate limit for /download_url endpoint (important).
                _sleep(sleep_download_url)

                try:
                    dl_url = _get_download_url(session, fid)
                except FatalHTTPError as exc:
                    print(f"[fatal] file_id={fid} {exc}")
                    _append_manifest(
                        manifest_path,
                        {
                            "file_id": fid,
                            "original_name": original_name,
                            "topic_id": t_id,
                            "topic_create_time": t_ct_raw,
                            "downloaded_at": None,
                            "saved_path": str(final_path),
                            "status": "fail",
                            "reason": str(exc),
                        },
                    )
                    return 3
                except Exception as exc:
                    counters.failed += 1
                    _append_manifest(
                        manifest_path,
                        {
                            "file_id": fid,
                            "original_name": original_name,
                            "topic_id": t_id,
                            "topic_create_time": t_ct_raw,
                            "downloaded_at": None,
                            "saved_path": str(final_path),
                            "status": "fail",
                            "reason": f"download_url_error: {exc}",
                        },
                    )
                    continue

                try:
                    _download_stream_to_file(session, dl_url, final_path)
                    counters.downloaded += 1
                    local_by_id[fid] = final_path
                    local_by_name[normalize_name_for_match(final_path.name)] = final_path
                    if dk_key:
                        local_by_dk[dk_key] = final_path
                    if resume and fid not in downloaded_ids:
                        downloaded_ids.add(fid)
                        _save_resume_state(resume_path, downloaded_ids)
                    _append_manifest(
                        manifest_path,
                        {
                            "file_id": fid,
                            "original_name": original_name,
                            "topic_id": t_id,
                            "topic_create_time": t_ct_raw,
                            "downloaded_at": datetime.now(tz=timezone.utc).isoformat(),
                            "saved_path": str(final_path),
                            "status": "success",
                            "reason": None,
                        },
                    )
                    if max_downloads is not None and counters.downloaded >= max_downloads:
                        stop_due_to_max_downloads = True
                        break
                except FatalHTTPError as exc:
                    # 403/401 during download: fail fast to avoid repeated hitting.
                    counters.failed += 1
                    _append_manifest(
                        manifest_path,
                        {
                            "file_id": fid,
                            "original_name": original_name,
                            "topic_id": t_id,
                            "topic_create_time": t_ct_raw,
                            "downloaded_at": None,
                            "saved_path": str(final_path),
                            "status": "fail",
                            "reason": str(exc),
                        },
                    )
                    print(
                        "[risk-control] Download got 401/403. "
                        "建议：确认已加入该星球、登录态未过期(Authorization/Cookie)；或稍后重试并加大 ZSXQ_SLEEP_DOWNLOAD_URL。"
                    )
                    return 3
                except Exception as exc:
                    counters.failed += 1
                    _append_manifest(
                        manifest_path,
                        {
                            "file_id": fid,
                            "original_name": original_name,
                            "topic_id": t_id,
                            "topic_create_time": t_ct_raw,
                            "downloaded_at": None,
                            "saved_path": str(final_path),
                            "status": "fail",
                            "reason": f"download_error: {exc}",
                        },
                    )
                    continue

            if stop_due_to_max_downloads:
                break

        _print_progress(counters)

        if reached_since_boundary:
            break
        if stop_due_to_max_downloads:
            print(f"max_downloads_reached={max_downloads}")
            break

        # Compute next end_time using the last topic in this page (API order is usually newest->oldest).
        # NOTE: Some zsxq API environments behave more reliably when using the exact `create_time`
        # as the next `end_time` (inclusive paging). We dedupe by file_id anyway.
        last_create_time = _topic_create_time(topics[-1])
        if not last_create_time:
            break
        if end_time == last_create_time:
            # Safety: avoid infinite loops when server returns same page repeatedly.
            break
        end_time = last_create_time

        if since_dt:
            try:
                last_dt = parse_zsxq_time(last_create_time)
            except Exception:
                break
            if last_dt < since_dt:
                break

        _sleep(sleep_topics)

    print("done")
    _print_progress(counters)
    if resume:
        print(f"resume_state={resume_path} downloaded_file_ids={len(downloaded_ids)}")
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

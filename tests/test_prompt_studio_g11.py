from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient

from quant_eam.api.app import app


def _write_prompt(path: Path, *, version: str, output_schema_version: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        f"prompt_version: {version}\n"
        f"output_schema_version: {output_schema_version}\n"
        "---\n"
        f"{body.rstrip()}\n"
    )
    path.write_text(text, encoding="utf-8")


def _setup_env(tmp_path: Path, monkeypatch) -> tuple[Path, Path, Path]:
    prompt_root = tmp_path / "prompts" / "agents"
    art_root = tmp_path / "artifacts"
    job_root = tmp_path / "jobs"
    prompt_root.mkdir(parents=True)
    art_root.mkdir(parents=True)
    job_root.mkdir(parents=True)

    monkeypatch.setenv("EAM_PROMPTS_ROOT", str(prompt_root))
    monkeypatch.setenv("EAM_ARTIFACT_ROOT", str(art_root))
    monkeypatch.setenv("EAM_JOB_ROOT", str(job_root))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    monkeypatch.setenv("EAM_WRITE_AUTH_MODE", "off")

    _write_prompt(
        prompt_root / "intent_agent_v1" / "prompt_v1.md",
        version="v1",
        output_schema_version="blueprint_v1",
        body="intent prompt v1",
    )
    _write_prompt(
        prompt_root / "intent_agent_v1" / "prompt_v2.md",
        version="v2",
        output_schema_version="blueprint_v1",
        body="intent prompt v2",
    )
    return prompt_root, art_root, job_root


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s:
            continue
        rows.append(json.loads(s))
    return rows


def _basic(user: str, passwd: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{passwd}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_g11_prompts_pages_render(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    client = TestClient(app)

    r = client.get("/ui/prompts")
    assert r.status_code == 200
    assert "intent_agent_v1" in r.text
    assert "v1, v2" in r.text

    r = client.get("/ui/prompts/intent_agent_v1")
    assert r.status_code == 200
    assert "Prompt intent_agent_v1" in r.text
    assert "intent prompt v2" in r.text
    assert "v1" in r.text and "v2" in r.text


def test_g11_publish_vn_plus_1_writes_overlay_and_audit(tmp_path: Path, monkeypatch) -> None:
    _prompt_root, art_root, _job_root = _setup_env(tmp_path, monkeypatch)
    client = TestClient(app)

    r = client.post(
        "/ui/prompts/intent_agent_v1/publish",
        data={
            "base_version": "v2",
            "output_schema_version": "blueprint_v1",
            "body": "intent prompt v3",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    assert (r.headers.get("location") or "").endswith("/ui/prompts/intent_agent_v1?version=v3")

    overlay = art_root / "prompt_overrides" / "agents" / "intent_agent_v1" / "prompt_v3.md"
    assert overlay.is_file()
    txt = overlay.read_text(encoding="utf-8")
    assert "prompt_version: v3" in txt
    assert "output_schema_version: blueprint_v1" in txt
    assert "intent prompt v3" in txt

    audit = art_root / "audit" / "prompt_events.jsonl"
    rows = _read_jsonl(audit)
    assert rows
    assert rows[-1].get("event_type") == "prompt_publish"
    assert rows[-1].get("prompt_version") == "v3"


def test_g11_publish_non_n_plus_1_or_stale_base_fails(tmp_path: Path, monkeypatch) -> None:
    _prompt_root, _art_root, _job_root = _setup_env(tmp_path, monkeypatch)
    client = TestClient(app)

    # base_version must match latest(v2).
    r = client.post(
        "/ui/prompts/intent_agent_v1/publish",
        data={
            "base_version": "v1",
            "output_schema_version": "blueprint_v1",
            "body": "invalid publish",
        },
        follow_redirects=False,
    )
    assert r.status_code == 409

    # Publish v3 first.
    r2 = client.post(
        "/ui/prompts/intent_agent_v1/publish",
        data={
            "base_version": "v2",
            "output_schema_version": "blueprint_v1",
            "body": "intent prompt v3",
        },
        follow_redirects=False,
    )
    assert r2.status_code == 303

    # Stale base_version behaves as duplicate/stale publish request and must fail.
    r3 = client.post(
        "/ui/prompts/intent_agent_v1/publish",
        data={
            "base_version": "v2",
            "output_schema_version": "blueprint_v1",
            "body": "intent prompt stale",
        },
        follow_redirects=False,
    )
    assert r3.status_code == 409


def test_g11_pin_writes_job_outputs_and_audit(tmp_path: Path, monkeypatch) -> None:
    _prompt_root, art_root, job_root = _setup_env(tmp_path, monkeypatch)
    client = TestClient(app)

    job_id = "a1b2c3d4e5f6"
    job_dir = job_root / job_id
    (job_dir / "outputs").mkdir(parents=True)
    (job_dir / "job_spec.json").write_text("{}\n", encoding="utf-8")

    r = client.post(
        "/ui/prompts/intent_agent_v1/pin",
        data={
            "job_id": job_id,
            "prompt_version": "v2",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text

    pin_events = job_dir / "outputs" / "prompts" / "prompt_pin_events.jsonl"
    pin_state = job_dir / "outputs" / "prompts" / "prompt_pin_state.json"
    assert pin_events.is_file()
    assert pin_state.is_file()

    ev_rows = _read_jsonl(pin_events)
    assert ev_rows[-1]["event_type"] == "prompt_pin"
    assert ev_rows[-1]["agent_id"] == "intent_agent_v1"
    assert ev_rows[-1]["prompt_version"] == "v2"

    state = json.loads(pin_state.read_text(encoding="utf-8"))
    assert state["schema_version"] == "prompt_pin_state_v1"
    assert state["job_id"] == job_id
    assert state["pins"]["intent_agent_v1"]["prompt_version"] == "v2"

    audit = art_root / "audit" / "prompt_events.jsonl"
    rows = _read_jsonl(audit)
    assert rows[-1]["event_type"] == "prompt_pin"
    assert rows[-1]["job_id"] == job_id


def test_g11_write_endpoints_require_auth_in_basic_mode(tmp_path: Path, monkeypatch) -> None:
    _prompt_root, art_root, job_root = _setup_env(tmp_path, monkeypatch)
    monkeypatch.setenv("EAM_WRITE_AUTH_MODE", "basic")
    monkeypatch.setenv("EAM_WRITE_AUTH_USER", "u1")
    monkeypatch.setenv("EAM_WRITE_AUTH_PASS", "p1")
    client = TestClient(app)

    # publish unauthorized
    r = client.post(
        "/ui/prompts/intent_agent_v1/publish",
        data={"base_version": "v2", "output_schema_version": "blueprint_v1", "body": "auth publish"},
        follow_redirects=False,
    )
    assert r.status_code == 401

    # publish authorized
    r2 = client.post(
        "/ui/prompts/intent_agent_v1/publish",
        data={"base_version": "v2", "output_schema_version": "blueprint_v1", "body": "auth publish"},
        headers=_basic("u1", "p1"),
        follow_redirects=False,
    )
    assert r2.status_code == 303
    assert (art_root / "prompt_overrides" / "agents" / "intent_agent_v1" / "prompt_v3.md").is_file()

    job_id = "b1b2b3b4b5b6"
    job_dir = job_root / job_id
    (job_dir / "outputs").mkdir(parents=True)
    (job_dir / "job_spec.json").write_text("{}\n", encoding="utf-8")

    # pin unauthorized
    r3 = client.post(
        "/ui/prompts/intent_agent_v1/pin",
        data={"job_id": job_id, "prompt_version": "v2"},
        follow_redirects=False,
    )
    assert r3.status_code == 401

    # pin authorized
    r4 = client.post(
        "/ui/prompts/intent_agent_v1/pin",
        data={"job_id": job_id, "prompt_version": "v2"},
        headers=_basic("u1", "p1"),
        follow_redirects=False,
    )
    assert r4.status_code == 303
    assert (job_dir / "outputs" / "prompts" / "prompt_pin_state.json").is_file()

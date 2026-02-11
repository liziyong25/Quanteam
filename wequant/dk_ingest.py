from __future__ import annotations

# Backward-compatible CLI wrapper.
# Implementation lives in `wequant/wesu/dk_ingest.py`.

from wequant.wesu import dk_ingest as _impl

__all__ = [name for name in dir(_impl) if not (name.startswith("__") and name.endswith("__"))]
for _name in __all__:
    globals()[_name] = getattr(_impl, _name)


def __getattr__(name: str):
    return getattr(_impl, name)


def main(argv=None) -> int:
    return _impl.main(argv)


if __name__ == "__main__":
    raise SystemExit(_impl.main())

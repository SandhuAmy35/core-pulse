from __future__ import annotations

try:
    from .zmq_broadcaster import main
except ImportError:
    from zmq_broadcaster import main


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "uvicorn is not installed.\n\n"
            "From the repo root run:\n"
            "  bash install_and_run.sh\n"
        ) from exc

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8010"))
    uvicorn.run("opentrader.main:app", host=host, port=port, reload=False)

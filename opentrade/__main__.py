from __future__ import annotations

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "uvicorn is not installed.\n\n"
            "Quick fix (recommended):\n"
            "  bash scripts/setup_opentrade.sh\n"
            "  bash scripts/run_opentrade.sh\n\n"
            "Or manually:\n"
            "  python3 -m venv .venv && source .venv/bin/activate\n"
            "  pip install -r requirements.txt\n"
            "  python3 -m uvicorn opentrade.main:app --host 127.0.0.1 --port 8010\n"
        ) from exc

    uvicorn.run("opentrade.main:app", host="127.0.0.1", port=8010, reload=False)

import subprocess
from pathlib import Path


def test_django_frontend_e2e_script():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["bash", str(root / "scripts/test_django_frontend_e2e.sh")],
        check=True,
        capture_output=True,
        text=True,
    )

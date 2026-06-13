#!/usr/bin/env bash
# Create mock ~/OpenTrader for CI-style testing of django frontend patch.
set -euo pipefail
ROOT="${1:-/tmp/OpenTrader-test}"
rm -rf "$ROOT"
mkdir -p "$ROOT/opentrader" "$ROOT/market" "$ROOT/frontend/dist/assets"

cat > "$ROOT/manage.py" << 'EOF'
#!/usr/bin/env python
import os, sys
def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "opentrader.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
if __name__ == "__main__":
    main()
EOF

cat > "$ROOT/opentrader/__init__.py" << 'EOF'
EOF

cat > "$ROOT/opentrader/settings.py" << 'EOF'
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "test"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.staticfiles", "market"]
MIDDLEWARE = []
ROOT_URLCONF = "opentrader.urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
EOF

cat > "$ROOT/opentrader/urls.py" << 'EOF'
from django.urls import path
from market.views import api_health

urlpatterns = [
    path("api/health/", api_health),
]
EOF

cat > "$ROOT/market/__init__.py" << 'EOF'
EOF

cat > "$ROOT/market/views.py" << 'EOF'
from django.http import JsonResponse

def api_health(_request):
    return JsonResponse({"status": "ok", "app": "OpenTrader-test"})
EOF

cat > "$ROOT/market/apps.py" << 'EOF'
from django.apps import AppConfig
class MarketConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "market"
EOF

cat > "$ROOT/frontend/dist/index.html" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Open Trader - BTCUSD</title>
  <link rel="stylesheet" href="/assets/index.css" />
</head>
<body>
  <div id="root">Loading chart...</div>
  <script type="module" src="/assets/index.js"></script>
</body>
</html>
EOF

cat > "$ROOT/frontend/dist/assets/index.js" << 'EOF'
document.getElementById("root").textContent = "OpenTrader chart OK";
document.title = "Open Trader - BTCUSD";
EOF

cat > "$ROOT/frontend/dist/assets/index.css" << 'EOF'
body { background: #0b0f17; color: #e8eefc; font-family: sans-serif; }
EOF

echo "django>=4.2" > "$ROOT/requirements.txt"
echo "Created mock OpenTrader at $ROOT"

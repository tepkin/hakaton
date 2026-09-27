#!/usr/bin/env bash
# GreenPlan AI - universal Linux launcher (Ubuntu / MosTech.OS / ROSA), NO sudo.
# Self-heals CRLF/BOM; bootstraps pip if missing (ensurepip -> get-pip);
# picks requirements-py38.txt on Python 3.8; venv fallback.
set -u

if [ -n "$(head -n 1 "$0" 2>/dev/null | tr -d -c '\r')" ]; then
  export GP_HOME="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
  tmp="$(mktemp /tmp/gp_run.XXXXXX)" || exit 1
  sed -e '1s/^\xEF\xBB\xBF//' -e 's/\r$//' "$0" > "$tmp"
  chmod +x "$tmp" 2>/dev/null
  exec /bin/sh "$tmp" "$@"
fi

cd "${GP_HOME:-$(dirname "$0")}" || exit 1
[ -d app ] || { echo "[ERROR] run.sh must sit in the project root (next to app/)."; exit 1; }

have_deps() { "$1" -c "import ezdxf, shapely, fastapi, uvicorn" >/dev/null 2>&1; }
have_pip()  { "$1" -m pip --version >/dev/null 2>&1; }

BASE=""
for c in python3.12 python3.11 python3.10 python3.9 python3 python; do
  command -v "$c" >/dev/null 2>&1 && { BASE="$c"; break; }
done
[ -n "$BASE" ] || { echo "[ERROR] python3 not found. Install python3 via package manager."; exit 1; }
VER=$("$BASE" -c 'import sys;print("%d.%d"%sys.version_info[:2])')
echo "[1/3] Python: $($BASE -V 2>&1)"

REQ=requirements.txt
if [ "$VER" = "3.8" ] && [ -f requirements-py38.txt ]; then REQ=requirements-py38.txt; fi

PY=""
have_deps "$BASE" && PY="$BASE"

# bootstrap pip without sudo: ensurepip -> version-matched get-pip.py
if [ -z "$PY" ] && ! have_pip "$BASE"; then
  echo "[2/3] pip not found - bootstrapping (no sudo) ..."
  "$BASE" -m ensurepip --user >/dev/null 2>&1 || true
  if ! have_pip "$BASE"; then
    GP_URL="https://bootstrap.pypa.io/get-pip.py"
    case "$VER" in
      3.7|3.8) GP_URL="https://bootstrap.pypa.io/pip/$VER/get-pip.py" ;;
    esac
    if command -v curl >/dev/null 2>&1; then curl -fsSL "$GP_URL" -o /tmp/get-pip.py
    elif command -v wget >/dev/null 2>&1; then wget -q "$GP_URL" -O /tmp/get-pip.py; fi
    [ -f /tmp/get-pip.py ] && "$BASE" /tmp/get-pip.py --user >/dev/null 2>&1
  fi
fi

if [ -z "$PY" ] && have_pip "$BASE"; then
  echo "[2/3] Installing dependencies ($REQ) ..."
  "$BASE" -m pip install --user -q -r "$REQ" >/dev/null 2>&1 || "$BASE" -m pip install --user -q -r "$REQ"
  have_deps "$BASE" && PY="$BASE"
fi

# venv fallback (if user-site is blocked)
if [ -z "$PY" ]; then
  [ -x .venv/bin/python ] || "$BASE" -m venv .venv >/dev/null 2>&1 || "$BASE" -m venv --without-pip .venv >/dev/null 2>&1 || true
  if [ -x .venv/bin/python ]; then
    have_pip .venv/bin/python || .venv/bin/python -m ensurepip >/dev/null 2>&1 || true
    if have_pip .venv/bin/python; then
      .venv/bin/python -m pip install -q -r "$REQ" >/dev/null 2>&1 || .venv/bin/python -m pip install -q -r "$REQ"
      have_deps .venv/bin/python && PY=.venv/bin/python
    fi
  fi
fi

[ -n "$PY" ] || { echo "[ERROR] Could not prepare pip+dependencies.";
  echo "        Options: install python3-pip via package manager (sudo apt/dnf/urpmi install python3-pip),";
  echo "        or check internet access for get-pip bootstrap."; exit 1; }

echo "[3/3] Server: http://127.0.0.1:8000   Swagger: http://127.0.0.1:8000/docs   (Ctrl+C to stop)"
[ -f examples/sample_input.dxf ] || "$PY" examples/make_sample_dxf.py >/dev/null 2>&1 || true
(sleep 3; command -v xdg-open >/dev/null 2>&1 && xdg-open http://127.0.0.1:8000 >/dev/null 2>&1 || true) &
"$PY" serve.py
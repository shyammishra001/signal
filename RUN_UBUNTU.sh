#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "===================================================="
echo " SHYAM AI - F&O EXPLOSION SCANNER V2.5 (Ubuntu)"
echo "===================================================="

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: Python 3 उपलब्ध नहीं है। पहले Python 3 और venv install करें:"
  echo "  sudo apt update"
  echo "  sudo apt install -y python3 python3-venv python3-pip"
  exit 1
fi

PYTHON_BIN="$(command -v python3)"
if ! "$PYTHON_BIN" -c 'import venv' >/dev/null 2>&1; then
  echo "ERROR: python3-venv उपलब्ध नहीं है। यह command चलाएँ:"
  echo "  sudo apt update && sudo apt install -y python3-venv python3-pip"
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "पहली बार Python virtual environment बनाया जा रहा है..."
  "$PYTHON_BIN" -m venv .venv
fi

VENV_PY=".venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "ERROR: .venv अधूरा है। .venv folder हटाकर script दोबारा चलाएँ।"
  exit 1
fi

# Dependencies are installed once. Reinstall only if requirements or Python runtime changes.
PY_TAG="$("$VENV_PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
REQ_HASH="$(sha256sum requirements.txt | awk '{print $1}')"
INSTALL_TAG="${PY_TAG}:${REQ_HASH}"
MARKER=".venv/.shyam_requirements_installed"
CURRENT_TAG="$(cat "$MARKER" 2>/dev/null || true)"
if [[ "$CURRENT_TAG" != "$INSTALL_TAG" ]] || ! "$VENV_PY" -c 'import streamlit, pandas, requests, streamlit_autorefresh' >/dev/null 2>&1; then
  echo "पहली बार / requirements बदलने पर ही packages install होंगे..."
  "$VENV_PY" -m pip install --upgrade "pip<25.1"
  "$VENV_PY" -m pip install -r requirements.txt
  if "$VENV_PY" -c 'import sys; raise SystemExit(0 if sys.version_info < (3, 9) else 1)'; then
    "$VENV_PY" -m pip install "pandas==2.0.3" "backports.zoneinfo"
  else
    "$VENV_PY" -m pip install "pandas>=2.2"
  fi
  "$VENV_PY" -c 'import streamlit, pandas, requests, streamlit_autorefresh; from zoneinfo import ZoneInfo' 2>/dev/null ||     "$VENV_PY" -c 'import streamlit, pandas, requests, streamlit_autorefresh; from backports.zoneinfo import ZoneInfo'
  printf '%s' "$INSTALL_TAG" > "$MARKER"
else
  echo "Packages पहले से installed हैं — दोबारा download/install नहीं होंगे।"
fi

echo
echo "Dashboard शुरू हो रहा है: http://127.0.0.1:8501"
echo "इसे रोकने के लिए इस Terminal में Ctrl+C दबाएँ।"
echo "API token केवल अपने कंप्यूटर पर डालें; किसी से साझा न करें।"
echo
exec "$VENV_PY" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false

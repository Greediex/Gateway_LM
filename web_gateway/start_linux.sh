#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="python3"
if [[ -x .venv-graph/bin/python ]]; then
  PYTHON=".venv-graph/bin/python"
elif [[ -x .venv/bin/python ]]; then
  PYTHON=".venv/bin/python"
fi
"$PYTHON" -m web_gateway.server "$@"

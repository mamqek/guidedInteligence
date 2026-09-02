#!/usr/bin/env bash
set -euo pipefail

skip_npm=0
skip_python=0
skip_qdrant_pull=0

for arg in "$@"; do
  case "$arg" in
    --skip-npm)
      skip_npm=1
      ;;
    --skip-python)
      skip_python=1
      ;;
    --skip-qdrant-pull)
      skip_qdrant_pull=1
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/setup.sh [--skip-npm] [--skip-python] [--skip-qdrant-pull]

Installs Guided Intelligence dependencies into the repository:
  - Node packages via npm ci
  - Python packages into .venv
  - local .env from .env.example when missing
  - default workspace web config
  - optional Qdrant Docker image pull
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

step() {
  printf '\n==> %s\n' "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$2" >&2
    exit 1
  fi
}

python_cmd=""
find_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        python_cmd="$candidate"
        return
      fi
    fi
  done

  echo "Python 3.11 or newer is required. Install it, then rerun scripts/setup.sh." >&2
  exit 1
}

bootstrap_pip() {
  mkdir -p .tmp
  "$python_cmd" - <<'PY'
from pathlib import Path
from urllib.request import urlretrieve

target = Path(".tmp/get-pip.py")
urlretrieve("https://bootstrap.pypa.io/get-pip.py", target)
PY
  .venv/bin/python .tmp/get-pip.py
}

step "Checking required tools"
require_command node "Node.js 22.12 or newer is required. Install Node 24, then rerun scripts/setup.sh."
require_command npm "npm is required and should be installed with Node.js."

node_version="$(node -p 'process.versions.node')"
node_major="${node_version%%.*}"
node_rest="${node_version#*.}"
node_minor="${node_rest%%.*}"
if [ "$node_major" -lt 22 ] || { [ "$node_major" -eq 22 ] && [ "$node_minor" -lt 12 ]; }; then
  echo "Node.js 22.12 or newer with node:sqlite is required. Found: $(node --version)." >&2
  exit 1
fi
if ! node -e "require('node:sqlite')" >/dev/null 2>&1; then
  echo "The selected Node runtime does not provide node:sqlite. Install Node 24, then rerun scripts/setup.sh." >&2
  exit 1
fi

find_python
echo "Node: $(node --version)"
echo "npm: $(npm --version)"
echo "Python: $($python_cmd --version)"

if [ "$skip_npm" -eq 0 ]; then
  step "Installing Node dependencies"
  npm ci
fi

if [ "$skip_python" -eq 0 ]; then
  step "Creating Python virtual environment"
  if [ ! -x ".venv/bin/python" ]; then
    rm -rf .venv
    if ! "$python_cmd" -m venv .venv; then
      echo "Standard venv creation failed; retrying without ensurepip and bootstrapping pip."
      rm -rf .venv
      "$python_cmd" -m venv --without-pip .venv
      bootstrap_pip
    fi
  fi

  if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    bootstrap_pip
  fi

  step "Installing Python dependencies"
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

step "Preparing local configuration"
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Configure embeddings/OAuth there; LLM API keys are entered in the Workspace tab."
else
  echo ".env already exists; leaving it unchanged."
fi

mkdir -p .guided-intelligence
cp configs/web-ui/workspace.json .guided-intelligence/config.json

if [ "$skip_qdrant_pull" -eq 0 ]; then
  step "Preparing Qdrant Docker image"
  if command -v docker >/dev/null 2>&1; then
    docker compose -f docker-compose.qdrant.yml pull
  else
    echo "Warning: Docker was not found. Qdrant will not start until Docker is installed and running." >&2
  fi
fi

printf '\nSetup complete.\n'
echo "Run manual testing with: bash scripts/run-dev.sh"

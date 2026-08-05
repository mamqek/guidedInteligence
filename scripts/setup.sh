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

step "Checking required tools"
require_command node "Node.js 22.x is required. Install Node 22, then rerun scripts/setup.sh."
require_command npm "npm is required and should be installed with Node.js."

node_major="$(node -p "Number(process.versions.node.split('.')[0])")"
if [ "$node_major" != "22" ]; then
  echo "Node.js 22.x is required. Found: $(node --version)." >&2
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
  if [ ! -d ".venv" ]; then
    "$python_cmd" -m venv .venv
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

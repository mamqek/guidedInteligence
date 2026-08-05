#!/usr/bin/env bash
set -euo pipefail

workspace_root=""
skip_qdrant=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --workspace-root)
      if [ "$#" -lt 2 ]; then
        echo "--workspace-root requires a path." >&2
        exit 2
      fi
      workspace_root="$2"
      shift 2
      ;;
    --skip-qdrant)
      skip_qdrant=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: bash scripts/run-dev.sh [--workspace-root PATH] [--skip-qdrant]

Starts Qdrant, the local retrieval backend, and the Vite frontend for manual testing.
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing .venv. Run scripts/setup.sh first." >&2
  exit 1
fi

if [ ! -d "node_modules" ]; then
  echo "Missing node_modules. Run scripts/setup.sh first." >&2
  exit 1
fi

if [ ! -f ".guided-intelligence/config.json" ]; then
  mkdir -p .guided-intelligence
  cp configs/web-ui/workspace.json .guided-intelligence/config.json
fi

if [ -z "$workspace_root" ]; then
  workspace_root="$repo_root"
fi
workspace_root="$(cd "$workspace_root" && pwd)"

port_open() {
  node -e '
    const net = require("net");
    const port = Number(process.argv[1]);
    const socket = net.createConnection({ host: "127.0.0.1", port });
    socket.setTimeout(300);
    socket.on("connect", () => { socket.destroy(); process.exit(0); });
    socket.on("timeout", () => { socket.destroy(); process.exit(1); });
    socket.on("error", () => process.exit(1));
  ' "$1" >/dev/null 2>&1
}

backend_healthy() {
  node -e '
    fetch("http://127.0.0.1:8790/health", { signal: AbortSignal.timeout(2000) })
      .then((response) => process.exit(response.ok ? 0 : 1))
      .catch(() => process.exit(1));
  ' >/dev/null 2>&1
}

if [ "$skip_qdrant" -eq 0 ]; then
  if command -v docker >/dev/null 2>&1; then
    echo "Starting Qdrant with Docker Compose if needed..."
    docker compose -f docker-compose.qdrant.yml up -d
  else
    echo "Warning: Docker was not found. Workspace retrieval needs Qdrant; install/start Docker or rerun with --skip-qdrant for UI-only checks." >&2
  fi
fi

reuse_backend=0
if port_open 8790; then
  if backend_healthy; then
    reuse_backend=1
    echo "Using existing healthy backend on http://127.0.0.1:8790."
  else
    echo "Port 8790 is already in use, but /health did not respond. Stop that process before running scripts/run-dev.sh." >&2
    exit 1
  fi
fi

if port_open 5173; then
  echo "Port 5173 is already in use. Stop the existing frontend server before running scripts/run-dev.sh." >&2
  exit 1
fi

printf '\nStarting Guided Intelligence for manual testing:\n'
echo "  API: http://127.0.0.1:8790/health"
echo "  UI:  http://127.0.0.1:5173"
echo "  Backend logs: .tmp/retrieval-server.log"
printf '\nPress Ctrl+C in this terminal to stop both services.\n'

mkdir -p .tmp
backend_pid=""
if [ "$reuse_backend" -eq 0 ]; then
  .venv/bin/python -m services.retrieval.server \
    --workspace-root "$workspace_root" \
    --tool-root "$repo_root" \
    > .tmp/retrieval-server.log \
    2> .tmp/retrieval-server.err.log &
  backend_pid="$!"

  for _ in $(seq 1 30); do
    if backend_healthy; then
      break
    fi
    sleep 0.5
  done

  if ! backend_healthy; then
    if [ -n "$backend_pid" ]; then
      kill "$backend_pid" >/dev/null 2>&1 || true
    fi
    echo "Backend did not become healthy on http://127.0.0.1:8790. Check .tmp/retrieval-server.err.log." >&2
    exit 1
  fi
fi

cleanup() {
  if [ -n "$backend_pid" ]; then
    kill "$backend_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

npm run web:dev

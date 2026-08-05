[CmdletBinding()]
param(
    [string]$WorkspaceRoot = "",
    [int]$BackendPort = 8790,
    [int]$FrontendPort = 5173,
    [switch]$SkipQdrant
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Test-TcpPortOpen {
    param([Parameter(Mandatory = $true)][int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(300)) {
            return $false
        }
        $client.EndConnect($connect)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-BackendHealth {
    try {
        $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($ArgumentList -join ' ')"
    }
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Missing .venv. Run scripts/setup.ps1 first."
}

if (-not (Test-Path "node_modules")) {
    throw "Missing node_modules. Run scripts/setup.ps1 first."
}

if (-not (Test-Path ".guided-intelligence\config.json")) {
    Invoke-Native npm @("run", "config:web:workspace")
}

if (-not $WorkspaceRoot) {
    $WorkspaceRoot = $RepoRoot
}
$ResolvedWorkspaceRoot = Resolve-Path $WorkspaceRoot

if (-not $SkipQdrant) {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Host "Starting Qdrant with Docker Compose if needed..."
        Invoke-Native docker @("compose", "-f", "docker-compose.qdrant.yml", "up", "-d")
    } else {
        Write-Warning "Docker was not found. Workspace retrieval needs Qdrant; install/start Docker Desktop or rerun with -SkipQdrant for UI-only checks."
    }
}

$ReuseBackend = $false
if (Test-TcpPortOpen $BackendPort) {
    if (Test-BackendHealth) {
        $ReuseBackend = $true
        Write-Host "Using existing healthy backend on http://127.0.0.1:$BackendPort."
    } else {
        throw "Port $BackendPort is already in use, but /health did not respond. Stop that process before running npm run dev:all."
    }
}

if (Test-TcpPortOpen $FrontendPort) {
    throw "Port $FrontendPort is already in use. Stop the existing frontend server before running npm run dev:all."
}

Write-Host ""
Write-Host "Starting Guided Intelligence for manual testing:"
Write-Host "  API: http://127.0.0.1:$BackendPort/health"
Write-Host "  UI:  http://127.0.0.1:$FrontendPort"
Write-Host "  Backend logs: .tmp\retrieval-server.log"
Write-Host ""
Write-Host "Press Ctrl+C in this window to stop both services."

New-Item -ItemType Directory -Force ".tmp" | Out-Null
$BackendLog = Join-Path $RepoRoot ".tmp\retrieval-server.log"
$BackendErrorLog = Join-Path $RepoRoot ".tmp\retrieval-server.err.log"

$backend = $null
if (-not $ReuseBackend) {
    $backend = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
        -ArgumentList @("-m", "services.retrieval.server", "--workspace-root", "$ResolvedWorkspaceRoot", "--tool-root", "$RepoRoot", "--port", "$BackendPort") `
        -WorkingDirectory "$RepoRoot" `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$BackendLog" `
        -RedirectStandardError "$BackendErrorLog" `
        -PassThru

    for ($i = 0; $i -lt 30; $i++) {
        if (Test-BackendHealth) {
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not (Test-BackendHealth)) {
        if ($backend -and -not $backend.HasExited) {
            Stop-Process -Id $backend.Id -Force
        }
        throw "Backend did not become healthy on http://127.0.0.1:$BackendPort. Check .tmp\retrieval-server.err.log."
    }
}

try {
    $env:GI_BACKEND_URL = "http://127.0.0.1:$BackendPort"
    $env:GI_FRONTEND_PORT = "$FrontendPort"
    Invoke-Native npm @("run", "web:dev")
} finally {
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force
    }
}

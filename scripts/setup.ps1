[CmdletBinding()]
param(
    [switch]$SkipNpm,
    [switch]$SkipPython,
    [switch]$SkipQdrantPull
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Test-CommandAvailable {
    param([Parameter(Mandatory = $true)][string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    Write-Host ""
    Write-Host "==> $Name"
    & $Action
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

function Get-PythonCommand {
    if (Test-CommandAvailable "py") {
        try {
            & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" | Out-Null
            return @{ Exe = "py"; Args = @("-3") }
        } catch {
        }
    }

    if (Test-CommandAvailable "python") {
        try {
            & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" | Out-Null
            return @{ Exe = "python"; Args = @() }
        } catch {
        }
    }

    throw "Python 3.11 or newer is required. Install it, then rerun scripts/setup.ps1."
}

Invoke-Step "Checking required tools" {
    if (-not (Test-CommandAvailable "node")) {
        throw "Node.js 22.12 or newer is required. Install Node 24, then rerun scripts/setup.ps1."
    }
    if (-not (Test-CommandAvailable "npm")) {
        throw "npm is required and should be installed with Node.js."
    }

    $nodeVersion = & node -p "process.versions.node"
    $nodeParts = $nodeVersion.Split('.')
    $nodeCompatible = ([int]$nodeParts[0] -gt 22) -or (([int]$nodeParts[0] -eq 22) -and ([int]$nodeParts[1] -ge 12))
    if (-not $nodeCompatible) {
        throw "Node.js 22.12 or newer with node:sqlite is required. Found: $(& node --version)."
    }
    & node -e "require('node:sqlite')"
    if ($LASTEXITCODE -ne 0) {
        throw "The selected Node runtime does not provide node:sqlite. Install Node 24, then rerun scripts/setup.ps1."
    }

    $script:PythonCommand = Get-PythonCommand
    Write-Host "Node: $(& node --version)"
    Write-Host "npm: $(& npm --version)"
    Write-Host "Python: $(& $script:PythonCommand.Exe @($script:PythonCommand.Args) --version)"
}

if (-not $SkipNpm) {
    Invoke-Step "Installing Node dependencies" {
        Invoke-Native npm @("ci")
    }
}

if (-not $SkipPython) {
    Invoke-Step "Creating Python virtual environment" {
        if (-not (Test-Path ".venv")) {
            Invoke-Native $script:PythonCommand.Exe @($script:PythonCommand.Args + @("-m", "venv", ".venv"))
        }
    }

    Invoke-Step "Installing Python dependencies" {
        Invoke-Native .\.venv\Scripts\python.exe @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Native .\.venv\Scripts\python.exe @("-m", "pip", "install", "-r", "requirements.txt")
    }
}

Invoke-Step "Preparing local configuration" {
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example. Configure embeddings/OAuth there; LLM API keys are entered in the Workspace tab."
    } else {
        Write-Host ".env already exists; leaving it unchanged."
    }

    Invoke-Native npm @("run", "config:web:workspace")
}

if (-not $SkipQdrantPull) {
    Invoke-Step "Preparing Qdrant Docker image" {
        if (Test-CommandAvailable "docker") {
            Invoke-Native docker @("compose", "-f", "docker-compose.qdrant.yml", "pull")
        } else {
            Write-Warning "Docker was not found. Qdrant will not start until Docker Desktop is installed and running."
        }
    }
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run manual testing with: npm run dev:all"

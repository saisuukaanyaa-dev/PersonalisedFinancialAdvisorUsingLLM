# Starts the Optimal Bank Deposit Finder MCP server (streamable-http transport).
#
# Usage:
#   .\start.ps1            # serve on http://127.0.0.1:8090/mcp
#   .\start.ps1 9000       # serve on a custom port
#   $env:MCP_PORT = 9000; .\start.ps1
#   .\start.ps1 dev        # open the MCP Inspector UI instead (mcp dev)
#   .\start.ps1 docker     # build and run the server in docker (compose)

param(
    [string]$Mode = ""
)

$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

# Folder holding the .py files (change here if it is ever renamed)
$SourceDir = "source"

$ServerFile = "$SourceDir/MCPServerForOptimalBankDepositFinderAgent.py"

if ($Mode -eq "docker") {
    if (-not (Test-Path ".env")) {
        Write-Error "Error: .env not found. Copy .env.example to .env and fill in the keys."
        exit 1
    }
    if (-not (Test-Path "memory.db")) {
        Write-Error "Error: memory.db not found. Run 'uv run python $SourceDir/DatabaseCreator.py' first."
        exit 1
    }
    $Port = if ($env:MCP_PORT) { $env:MCP_PORT } else { "8090" }
    $N8nPort = if ($env:N8N_PORT) { $env:N8N_PORT } else { "5678" }
    Write-Host "Starting MCP server on http://127.0.0.1:$Port/mcp and n8n on http://127.0.0.1:$N8nPort"
    docker compose up --build
    exit $LASTEXITCODE
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "Error: uv not found. Install it from https://docs.astral.sh/uv/"
    exit 1
}

$env:PYTHONIOENCODING = "utf-8"

if ($Mode -eq "dev") {
    uv run mcp dev $ServerFile
    exit $LASTEXITCODE
}

if ($Mode) {
    $env:MCP_PORT = $Mode
}
if (-not $env:MCP_PORT) {
    $env:MCP_PORT = "8090"
}

Write-Host "Starting MCP server on http://127.0.0.1:$($env:MCP_PORT)/mcp"
uv run python $ServerFile
exit $LASTEXITCODE

param(
    [string]$PythonExe = $env:PRISM_PYTHON
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$WebRoot = Join-Path $ProjectRoot "web"
$RuntimeRoot = Join-Path $ProjectRoot ".runtime"
$BackendPort = 8000
$FrontendPort = 3000

function Resolve-Python {
    param([string]$RequestedPython)

    if ($RequestedPython) {
        if (-not (Test-Path -LiteralPath $RequestedPython)) {
            throw "Python executable not found: $RequestedPython"
        }
        return (Resolve-Path -LiteralPath $RequestedPython).Path
    }

    if ($env:CONDA_PREFIX) {
        $CondaPython = Join-Path $env:CONDA_PREFIX "python.exe"
        if (Test-Path -LiteralPath $CondaPython) {
            return (Resolve-Path -LiteralPath $CondaPython).Path
        }
    }

    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        throw "Python was not found. Activate the PRism environment or pass -PythonExe <path-to-python>."
    }
    return $PythonCommand.Source
}

function Get-ListeningProcess {
    param([int]$Port)

    $Listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if (-not $Listeners) {
        return @()
    }
    return @($Listeners | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Stop-PrismListener {
    param(
        [int]$Port,
        [string]$Name,
        [string]$CommandPattern
    )

    foreach ($ProcessId in Get-ListeningProcess -Port $Port) {
        $ProcessInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
        $CommandLine = $ProcessInfo.CommandLine

        if (-not $CommandLine -or $CommandLine -notmatch $CommandPattern) {
            throw "Port $Port is occupied by a non-PRism process (PID $ProcessId): $CommandLine. Stop it manually, then run this script again."
        }

        Write-Host "Stopping existing PRism $Name process (PID $ProcessId)..."
        Stop-Process -Id $ProcessId -Force
    }

    $Deadline = (Get-Date).AddSeconds(10)
    while ((Get-ListeningProcess -Port $Port).Count -gt 0) {
        if ((Get-Date) -gt $Deadline) {
            throw "Port $Port was not released after stopping the existing PRism $Name process."
        }
        Start-Sleep -Milliseconds 250
    }
}

function Wait-ForHttpEndpoint {
    param(
        [string]$Url,
        [string]$Name
    )

    $Deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $Deadline) {
        try {
            Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 2 | Out-Null
            return
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "$Name did not become available at $Url. Check logs under $RuntimeRoot."
}

$PythonExe = Resolve-Python -RequestedPython $PythonExe
$NpmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $NpmCommand) {
    throw "npm.cmd was not found. Install Node.js 20+ and run this script again."
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

Stop-PrismListener -Port $BackendPort -Name "backend" -CommandPattern "(?i)uvicorn.*backend\.main:app"
Stop-PrismListener -Port $FrontendPort -Name "frontend" -CommandPattern "(?i)PRism[\\/]web[\\/]node_modules[\\/]next"

& $PythonExe -c "import fastapi, langfuse, langgraph, mcp, pydantic_settings" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing backend dependencies..."
    & $PythonExe -m pip install -r (Join-Path $ProjectRoot "backend\requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dependency installation failed."
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $WebRoot "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    Push-Location $WebRoot
    try {
        & $NpmCommand.Source ci
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend dependency installation failed."
        }
    } finally {
        Pop-Location
    }
}

Write-Host "Starting PRism backend on http://127.0.0.1:$BackendPort ..."
$BackendProcess = Start-Process -FilePath $PythonExe `
    -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
    -WorkingDirectory $ProjectRoot `
    -NoNewWindow `
    -PassThru

Wait-ForHttpEndpoint -Url "http://127.0.0.1:$BackendPort/health" -Name "Backend"

Write-Host "Starting PRism frontend on http://127.0.0.1:$FrontendPort ..."
$FrontendProcess = Start-Process -FilePath $NpmCommand.Source `
    -ArgumentList @("run", "dev", "--", "--hostname", "127.0.0.1", "--port", "$FrontendPort") `
    -WorkingDirectory $WebRoot `
    -NoNewWindow `
    -PassThru

Wait-ForHttpEndpoint -Url "http://127.0.0.1:$FrontendPort" -Name "Frontend"

Write-Host ""
Write-Host "PRism is running: http://127.0.0.1:$FrontendPort"
Write-Host "Press Ctrl+C to stop PRism."

try {
    Wait-Process -Id $BackendProcess.Id, $FrontendProcess.Id
} finally {
    foreach ($Process in @($BackendProcess, $FrontendProcess)) {
        if ($Process -and -not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

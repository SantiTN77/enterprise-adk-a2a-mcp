param(
    [ValidateSet("live", "self-verify", "static-infra")]
    [string]$Mode = "live",
    [switch]$AllowLocalhost
)

# Windows PowerShell 5.1 compatible runner for enterprise-adk-a2a-mcp E2E suite.
$ErrorActionPreference = "Stop"

$SuiteDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$UvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $UvCmd) {
    $CandidateUv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $CandidateUv) {
        $UvExe = $CandidateUv
    } else {
        Write-Error "uv CLI not found on PATH or $CandidateUv"
        exit 2
    }
} else {
    $UvExe = $UvCmd.Source
}

function Invoke-Uv {
    param([string[]]$UvArgs)
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $UvExe @UvArgs
    } finally {
        $ErrorActionPreference = $prevPref
    }
}

Push-Location $SuiteDir
try {
    if ($Mode -eq "live") {
        $requiredVars = @(
            "ORCHESTRATOR_URL",
            "FINANCIAL_AGENT_URL",
            "COMPLIANCE_AGENT_URL",
            "WEB_URL"
        )
        $missing = @()
        foreach ($v in $requiredVars) {
            $val = [System.Environment]::GetEnvironmentVariable($v)
            if ([string]::IsNullOrWhiteSpace($val)) {
                $missing += $v
            }
        }
        if ($missing.Count -gt 0) {
            Write-Host "[ANTI-CHEAT FAIL-FAST] Missing required live URL environment variable(s): $($missing -join ', ')" -ForegroundColor Red
            Write-Host "Live mode never falls back to mocks. Provide live URLs or run '-Mode self-verify' / '-Mode static-infra'." -ForegroundColor Yellow
            exit 2
        }

        if ($AllowLocalhost) {
            $env:E2E_ALLOW_LOCALHOST = "1"
        }

        Invoke-Uv -UvArgs @("sync", "--frozen")
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        Invoke-Uv -UvArgs @("run", "--frozen", "playwright", "install", "chromium")
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARN] playwright install chromium exited $LASTEXITCODE; continuing with cached/system Chrome fallback." -ForegroundColor Yellow
        }

        Invoke-Uv -UvArgs @("run", "--frozen", "pytest", "--ignore=test_self_verify.py", "-m", "live_e2e or static_repo")
        exit $LASTEXITCODE
    }

    if ($Mode -eq "self-verify") {
        Write-Host "========================================================================" -ForegroundColor Cyan
        Write-Host "[SELF-VERIFY ONLY] Offline harness verified test suite logic;" -ForegroundColor Cyan
        Write-Host "live GCP/Vercel deployment was NOT tested." -ForegroundColor Cyan
        Write-Host "========================================================================" -ForegroundColor Cyan

        Invoke-Uv -UvArgs @("sync", "--frozen")
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        Invoke-Uv -UvArgs @("run", "--frozen", "pytest", "test_self_verify.py", "-m", "self_verify")
        exit $LASTEXITCODE
    }

    if ($Mode -eq "static-infra") {
        Invoke-Uv -UvArgs @("sync", "--frozen")
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        Invoke-Uv -UvArgs @("run", "--frozen", "pytest", "--ignore=test_self_verify.py", "-m", "static_repo")
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

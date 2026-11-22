<#
.SYNOPSIS
    Deploys the isolated web/ Next.js App Router UI and OIDC BFF to Vercel production using pnpm.
    Compatible with Windows PowerShell 5.1+.
#>
[CmdletBinding()]
param(
    [string]$ProjectName = "enterprise-adk-a2a-mcp-web",
    [string]$OrchestratorUrl = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$webDir = Join-Path $repoRoot "web"
$parentVercel = Join-Path (Split-Path -Parent $repoRoot) ".vercel"

if (Test-Path $parentVercel) {
    Write-Warning "Parent workspace .vercel directory exists at $parentVercel; running strictly inside $webDir."
}

Push-Location $webDir
try {
    & vercel link --project $ProjectName --yes
    if ($LASTEXITCODE -ne 0) {
        throw "vercel link failed."
    }

    if (-not [string]::IsNullOrWhiteSpace($OrchestratorUrl)) {
        Write-Host "[INFO] Updating CLOUD_RUN_ORCHESTRATOR_URL on Vercel production..."
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & vercel env rm CLOUD_RUN_ORCHESTRATOR_URL production --yes 2>$null | Out-Null
        $ErrorActionPreference = $prevEap
        $OrchestratorUrl.Trim().TrimEnd('/') | & vercel env add CLOUD_RUN_ORCHESTRATOR_URL production
    }

    Write-Host "[INFO] Deploying web/ to Vercel production..."
    & vercel deploy --prod --yes
    if ($LASTEXITCODE -ne 0) {
        throw "vercel deploy --prod failed."
    }
} finally {
    Pop-Location
}

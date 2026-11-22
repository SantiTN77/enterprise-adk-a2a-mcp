<#
.SYNOPSIS
    Deploys GCP infrastructure and Cloud Build container images for enterprise-adk-a2a-mcp.
    Compatible with Windows PowerShell 5.1+.
#>
[CmdletBinding()]
param(
    [string]$ProjectId = "gen-lang-client-0527325883",
    [string]$Region = "us-central1",
    [string]$RepoName = "enterprise-adk-a2a-mcp",
    [string]$Tag = "",
    [switch]$SkipBuild,
    [switch]$PlanOnly,
    [switch]$AutoApprove
)

$ErrorActionPreference = "Stop"

function Assert-CommandExists {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Required CLI '$Name' was not found on PATH."
    }
}

function Ensure-GcpAuth {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $activeAccount = & gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>$null
    $authExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($authExit -eq 0 -and -not [string]::IsNullOrWhiteSpace(($activeAccount | Out-String))) {
        Write-Host "[OK] Active gcloud account: $($activeAccount.Trim())"
        return
    }

    if (-not [string]::IsNullOrWhiteSpace($env:CLOUDSDK_AUTH_ACCESS_TOKEN)) {
        Write-Host "[OK] Using existing CLOUDSDK_AUTH_ACCESS_TOKEN for non-interactive gcloud calls."
        return
    }

    $adcPath = Join-Path $env:APPDATA "gcloud\application_default_credentials.json"
    if (-not (Test-Path $adcPath)) {
        throw "No active gcloud account and no ADC file at $adcPath. Run 'gcloud auth login' and 'gcloud auth application-default login'."
    }

    $adc = Get-Content -Path $adcPath -Raw | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($adc.refresh_token) -or [string]::IsNullOrWhiteSpace($adc.client_id) -or [string]::IsNullOrWhiteSpace($adc.client_secret)) {
        throw "ADC file at $adcPath is missing refresh_token/client_id/client_secret. Run 'gcloud auth application-default login'."
    }

    $body = @{
        client_id     = $adc.client_id
        client_secret = $adc.client_secret
        refresh_token = $adc.refresh_token
        grant_type    = "refresh_token"
    }
    $tokenResp = Invoke-RestMethod -Method Post -Uri "https://oauth2.googleapis.com/token" -Body $body -UseBasicParsing
    if ([string]::IsNullOrWhiteSpace($tokenResp.access_token)) {
        throw "Failed to refresh GCP access token from ADC. Run 'gcloud auth login'."
    }
    $env:CLOUDSDK_AUTH_ACCESS_TOKEN = $tokenResp.access_token
    Write-Host "[OK] Refreshed ADC access token into CLOUDSDK_AUTH_ACCESS_TOKEN (gcloud auth list was empty)."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$tfDir = Join-Path $repoRoot "infra\terraform"
$tfStateDir = Join-Path $env:LOCALAPPDATA "enterprise-adk-a2a-mcp\tfstate"
if (-not (Test-Path $tfStateDir)) {
    New-Item -ItemType Directory -Path $tfStateDir -Force | Out-Null
}
$tfStatePath = Join-Path $tfStateDir "terraform.tfstate"
$legacyState = Join-Path $tfDir "terraform.tfstate"
if ((Test-Path $legacyState) -and -not (Test-Path $tfStatePath)) {
    Move-Item -Path $legacyState -Destination $tfStatePath -Force
}
$legacyBackup = Join-Path $tfDir "terraform.tfstate.backup"
if (Test-Path $legacyBackup) {
    Remove-Item -Path $legacyBackup -Force -ErrorAction SilentlyContinue
}

Assert-CommandExists -Name "gcloud"
Assert-CommandExists -Name "terraform"
Ensure-GcpAuth

Write-Host "[INFO] Configuring gcloud defaults for project '$ProjectId' and region '$Region'..."
& gcloud config set project $ProjectId | Out-Null
if ($LASTEXITCODE -ne 0) { throw "gcloud config set project failed." }
& gcloud config set run/region $Region | Out-Null
if ($LASTEXITCODE -ne 0) { throw "gcloud config set run/region failed." }
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& cmd /c "echo n | gcloud config set compute/region $Region >nul 2>&1"
$ErrorActionPreference = $prevEap

Write-Host "[INFO] Pre-enabling prerequisite GCP bootstrap APIs (cloudresourcemanager, serviceusage)..."
& gcloud services enable cloudresourcemanager.googleapis.com serviceusage.googleapis.com --project=$ProjectId
if ($LASTEXITCODE -ne 0) {
    throw "Failed to enable cloudresourcemanager.googleapis.com / serviceusage.googleapis.com. Enable them once in GCP Console or verify permissions."
}

if ([string]::IsNullOrWhiteSpace($Tag)) {
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCmd -and (Test-Path (Join-Path $repoRoot ".git"))) {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $null = & cmd /c "git -C `"$repoRoot`" rev-parse --verify HEAD >nul 2>&1"
        $headExit = $LASTEXITCODE
        $ErrorActionPreference = $prevEap
        if ($headExit -eq 0) {
            $Tag = (& git -C $repoRoot rev-parse --short HEAD).Trim()
        }
    }
    if ([string]::IsNullOrWhiteSpace($Tag)) {
        $Tag = Get-Date -Format "yyyyMMdd-HHmmss"
    }
}
Write-Host "[INFO] Using image tag: $Tag"

Write-Host "[INFO] Initializing and validating Terraform..."
& terraform -chdir="$tfDir" init
if ($LASTEXITCODE -ne 0) { throw "terraform init failed." }

& terraform -chdir="$tfDir" validate
if ($LASTEXITCODE -ne 0) { throw "terraform validate failed." }

$arHost = "$Region-docker.pkg.dev/$ProjectId/$RepoName"
$financialImage = "$arHost/adk-financial-agent`:$Tag"
$complianceImage = "$arHost/adk-compliance-agent`:$Tag"
$orchestratorImage = "$arHost/adk-orchestrator`:$Tag"

if (-not $SkipBuild) {
    Write-Host "[INFO] Pre-enabling Cloud Build & Artifact Registry APIs and creating AR repository..."
    & gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com --project=$ProjectId
    if ($LASTEXITCODE -ne 0) { throw "Failed to enable cloudbuild/artifactregistry APIs." }

    & terraform -chdir="$tfDir" apply -auto-approve `
        -state="$tfStatePath" `
        -target="google_project_service.apis" `
        -target="google_artifact_registry_repository.containers" `
        -var="project_id=$ProjectId" `
        -var="region=$Region" `
        -var="artifact_registry_repo=$RepoName"
    if ($LASTEXITCODE -ne 0) { throw "Targeted Terraform apply for APIs and Artifact Registry failed." }

    $serviceSpecs = @(
        @{ Dir = (Join-Path $repoRoot "services\financial_agent"); Image = $financialImage },
        @{ Dir = (Join-Path $repoRoot "services\compliance_agent"); Image = $complianceImage },
        @{ Dir = (Join-Path $repoRoot "services\orchestrator"); Image = $orchestratorImage }
    )

    foreach ($svc in $serviceSpecs) {
        if (-not (Test-Path $svc.Dir)) {
            throw "Service directory not found: $($svc.Dir). Pass -SkipBuild or implement services first."
        }
        Write-Host "[INFO] Building $($svc.Image) via Cloud Build..."
        & gcloud builds submit $svc.Dir --tag $svc.Image --project=$ProjectId --region=$Region
        if ($LASTEXITCODE -ne 0) {
            throw "gcloud builds submit failed for $($svc.Dir)."
        }
    }
}

$tfVars = @(
    "-state=$tfStatePath",
    "-var=project_id=$ProjectId",
    "-var=region=$Region",
    "-var=artifact_registry_repo=$RepoName",
    "-var=financial_agent_image=$financialImage",
    "-var=compliance_agent_image=$complianceImage",
    "-var=orchestrator_image=$orchestratorImage"
)

if ($PlanOnly) {
    Write-Host "[INFO] Running Terraform plan..."
    & terraform -chdir="$tfDir" plan @tfVars
    if ($LASTEXITCODE -ne 0) { throw "terraform plan failed." }
    exit 0
}

Write-Host "[INFO] Applying full Terraform stack..."
if ($AutoApprove) {
    & terraform -chdir="$tfDir" apply -auto-approve @tfVars
} else {
    & terraform -chdir="$tfDir" apply @tfVars
}
if ($LASTEXITCODE -ne 0) { throw "terraform apply failed." }

Write-Host "[INFO] Terraform Outputs Summary:"
& terraform -chdir="$tfDir" output -state="$tfStatePath" -json
if ($LASTEXITCODE -ne 0) { throw "terraform output failed." }

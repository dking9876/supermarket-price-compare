# Sync Script for Supermarket Price Compare
# Use this to prepare for migration to another computer

$brainFolder = "C:\Users\Daniel\.gemini\antigravity\brain\2ff318c8-b77f-4faf-b870-3d1a4d9c1620"
$repoBrain = ".agent/brain"
$secrets = @("credentials.env", ".env")

function Export-Context {
    Write-Host "Exporting brain artifacts to repository..." -ForegroundColor Cyan
    if (!(Test-Path $repoBrain)) { New-Item -ItemType Directory -Path $repoBrain -Force }
    Copy-Item -Path "$brainFolder\*" -Destination $repoBrain -Recurse -Force
    
    Write-Host "`nSecret Migration Notice:" -ForegroundColor Yellow
    Write-Host "I cannot automatically push secrets to Git for security."
    Write-Host "Please manually copy these files to your new PC's project folder:"
    foreach ($s in $secrets) {
        if (Test-Path $s) { Write-Host " - $s" -ForegroundColor Green }
    }
    
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "1. git add .agent/brain"
    Write-Host "2. git commit -m 'sync: update agent context'"
    Write-Host "3. git push"
}

function Import-Context {
    Write-Host "Importing brain artifacts from repository..." -ForegroundColor Cyan
    if (!(Test-Path $brainFolder)) { New-Item -ItemType Directory -Path $brainFolder -Force }
    Copy-Item -Path "$repoBrain\*" -Destination $brainFolder -Recurse -Force
    Write-Host "Context synced! I will now recognize our progress." -ForegroundColor Green
}

if ($args[0] -eq "import") {
    Import-Context
} else {
    Export-Context
}

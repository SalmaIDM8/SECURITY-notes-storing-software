<#
PowerShell helper to load backend/.env into the current process environment
and start the uvicorn dev server. Run this from the `backend` folder.

Usage (PowerShell):
  .\start-dev.ps1

Note: This script sets environment variables for the started uvicorn process
only in this session. To persist variables, add them to Windows Environment Variables.
#>

$envFile = Join-Path $PSScriptRoot '.env'
if (-Not (Test-Path $envFile)) {
  Write-Host "No .env file found at $envFile. Create one with required vars (see README)."
} else {
  Write-Host "Loading environment variables from $envFile"
  Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -match '^\s*#') { continue }
    if ($line -match '^\s*$') { continue }
    $parts = $line -split '=', 2
    if ($parts.Count -eq 2) {
      $name = $parts[0].Trim()
      $value = $parts[1].Trim().Trim('"').Trim("'")
      # Use Set-Item to write to the Env: drive with a dynamic name
      Set-Item -Path ("Env:" + $name) -Value $value
      Write-Host "Set $name"
    }
  }
}

# Ensure venv activation is done outside this script. Start the server:
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

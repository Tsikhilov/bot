Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)
. .\scripts\prod_tools.ps1

Write-Host "Copying hiddify_native_ru.py to production..."
Copy-ToProd "scripts/hiddify_native_ru.py" "/opt/SmartKamaVPN/scripts/hiddify_native_ru.py"

$remote = @"
set -e
chmod +x /opt/SmartKamaVPN/scripts/hiddify_native_ru.py
python3 /opt/SmartKamaVPN/scripts/hiddify_native_ru.py --apply --force-en-ru --nginx-reload --install-cron
systemctl is-active hiddify-nginx
"@

Write-Host "Applying native RU hardening on production..."
Invoke-ProdSSH $remote

Write-Host "DONE"

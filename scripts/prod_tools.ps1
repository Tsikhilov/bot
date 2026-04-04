$ProdHost = "72.56.100.45"
$ProdUser = "root"
$ProdPassword = "szFt1PugQ-5Hy-"
$Plink = "C:\Program Files\PuTTY\plink.exe"
$Pscp = "C:\Program Files\PuTTY\pscp.exe"

function Invoke-ProdSSH {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command
    )
    & $Plink -batch -pw $ProdPassword "$ProdUser@${ProdHost}" $Command
}

function Copy-ToProd {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LocalPath,
        [Parameter(Mandatory = $true)]
        [string]$RemotePath
    )
    & $Pscp -batch -pw $ProdPassword $LocalPath "$ProdUser@${ProdHost}:$RemotePath"
}

function Deploy-ProdBot {
    Copy-ToProd "UserBot/bot.py" "/opt/SmartKamaVPN/UserBot/bot.py"
    Copy-ToProd "scripts/shortlink_redirect.py" "/opt/SmartKamaVPN/scripts/shortlink_redirect.py"

    Invoke-ProdSSH "set -e; cd /opt/SmartKamaVPN; .venv/bin/python -m py_compile UserBot/bot.py scripts/shortlink_redirect.py; systemctl restart smartkamavpn smartkama-shortlink; systemctl is-active smartkamavpn; systemctl is-active smartkama-shortlink"
}

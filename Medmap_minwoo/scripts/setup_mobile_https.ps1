$ErrorActionPreference = 'Stop'

$medmapRoot = Split-Path -Parent $PSScriptRoot
$certificateDirectory = Join-Path $medmapRoot 'local-cache\mobile-https'
$openssl = 'C:\Program Files\Git\usr\bin\openssl.exe'

if (-not (Test-Path -LiteralPath $openssl)) {
    throw 'Git for Windows OpenSSL was not found.'
}

$localIp = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
    Where-Object {
        $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
        $_.IPAddressToString -ne '127.0.0.1' -and
        $_.IPAddressToString -notlike '169.254.*'
    } |
    ForEach-Object { $_.IPAddressToString } |
    Sort-Object @{ Expression = { if ($_ -match '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)') { 0 } else { 1 } } } |
    Select-Object -First 1

if (-not $localIp) {
    throw 'No local Wi-Fi or Ethernet IPv4 address was found.'
}

New-Item -ItemType Directory -Path $certificateDirectory -Force | Out-Null
$configPath = Join-Path $certificateDirectory 'server-openssl.cnf'

@"
[req]
prompt = no
distinguished_name = dn
req_extensions = extensions

[dn]
CN = $localIp

[extensions]
subjectAltName = @alt_names
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
IP.1 = $localIp
DNS.1 = localhost
"@ | Set-Content -LiteralPath $configPath -Encoding ascii

$caKey = Join-Path $certificateDirectory 'ca-key.pem'
$caCertificate = Join-Path $certificateDirectory 'ca-cert.pem'
$phoneCertificate = Join-Path $certificateDirectory 'medmap-local-ca.cer'
$serverKey = Join-Path $certificateDirectory 'server-key.pem'
$serverRequest = Join-Path $certificateDirectory 'server.csr'
$serverCertificate = Join-Path $certificateDirectory 'server-cert.pem'

& $openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 825 `
    -keyout $caKey -out $caCertificate -subj '/CN=MedMap Local Test CA' `
    -addext 'basicConstraints=critical,CA:TRUE' `
    -addext 'keyUsage=critical,keyCertSign,cRLSign'
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the local CA.' }

& $openssl req -new -newkey rsa:2048 -sha256 -nodes `
    -keyout $serverKey -out $serverRequest -config $configPath
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the server certificate request.' }

& $openssl x509 -req -sha256 -days 365 -in $serverRequest `
    -CA $caCertificate -CAkey $caKey -CAcreateserial -out $serverCertificate `
    -extensions extensions -extfile $configPath
if ($LASTEXITCODE -ne 0) { throw 'Failed to sign the server certificate.' }

& $openssl x509 -in $caCertificate -outform der -out $phoneCertificate
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the phone certificate file.' }

@{
    created_at = (Get-Date).ToString('o')
    local_ip = $localIp
    mobile_url = "https://${localIp}:5173"
    certificate_download_url = "http://${localIp}:8081/medmap-local-ca.cer"
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $certificateDirectory 'mobile-access.json') -Encoding utf8

Write-Host "Mobile URL: https://${localIp}:5173"
Write-Host "Certificate file: $phoneCertificate"
Write-Host 'All generated certificates are local test files and are excluded from Git.'

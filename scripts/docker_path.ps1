# Dùng chung cho docker_start.ps1 / docker_stop.ps1.
# Terminal (VS Code, PowerShell) mở TRƯỚC khi cài Docker Desktop giữ PATH cũ nên không thấy docker.exe.
# Nạp lại PATH từ registry, rồi thử thư mục cài mặc định của Docker Desktop.
function Find-Docker {
    if (Get-Command docker -ErrorAction SilentlyContinue) { return $true }
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
    if (Get-Command docker -ErrorAction SilentlyContinue) { return $true }
    $default = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'
    if (Test-Path (Join-Path $default 'docker.exe')) {
        $env:Path = "$default;$env:Path"
        return $true
    }
    return $false
}

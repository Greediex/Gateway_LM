Set-Location (Join-Path $PSScriptRoot '..')
if (Test-Path '.venv-graph\Scripts\python.exe') {
    & '.venv-graph\Scripts\python.exe' -m web_gateway.server @args
} elseif (Test-Path '.venv\Scripts\python.exe') {
    & '.venv\Scripts\python.exe' -m web_gateway.server @args
} else {
    py -m web_gateway.server @args
}

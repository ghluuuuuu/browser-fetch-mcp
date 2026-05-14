@echo off
setlocal

cd /d "%~dp0"

set "PYTHONUNBUFFERED=1"
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"

if not defined WEB_FETCH_MCP_CONFIG (
    set "WEB_FETCH_MCP_CONFIG=%~dp0config.example.yaml"
)

echo Starting Obscura Web Fetch MCP service...
echo Streamable HTTP: http://127.0.0.1:8000/mcp
echo SSE:             http://127.0.0.1:8000/sse
echo.

python -m obscura_web_fetch_mcp

endlocal

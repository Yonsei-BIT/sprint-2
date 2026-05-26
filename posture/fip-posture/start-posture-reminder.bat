@echo off
cd /d "%~dp0"
start "" "http://localhost:4174"
"C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" server.mjs

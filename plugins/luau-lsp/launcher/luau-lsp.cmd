@echo off
rem Windows launcher for this plugin's .lsp.json: Claude Code resolves launcher/luau-lsp to this file through PATHEXT.
rem find-luau-lsp.ps1 picks the binary and arguments in one PowerShell call; the binary then runs as a child of
rem this cmd.exe so the LSP stdin and stdout pass straight through. Nothing before :which may write to stdout.
setlocal DisableDelayedExpansion
set "LLSP_BIN="
set "LLSP_ARGS="
for /f "usebackq delims=" %%L in (`powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0find-luau-lsp.ps1" ^<NUL`) do set "%%L"
if not defined LLSP_BIN exit /b 127
if /i "%~1"=="--which" goto which
"%LLSP_BIN%" %LLSP_ARGS%
exit /b %ERRORLEVEL%

rem `luau-lsp.cmd --which` prints the command it would run, for checking an install from a terminal.
:which
echo "%LLSP_BIN%" %LLSP_ARGS%
exit /b 0

# Windows half of the launcher: luau-lsp.cmd runs this once and starts the binary itself, so stdio reaches the
# server directly. Prints LLSP_BIN=<path> and LLSP_ARGS=<command line>, or one line on stderr and exit 127.
# Search order and arguments mirror the POSIX launcher `luau-lsp` next to this file ([find:*] tags, checked by
# tests/test-launcher.py). Runs on Windows PowerShell 5.1: no ?? or ternary operators.
$ErrorActionPreference = 'Continue'
$ExtId = 'johnnymorganz.luau-lsp'
$VerRe = '^\d+\.\d+\.\d+$'

function Pick([string]$a, [string]$b) { if ($a) { $a } else { $b } }
function Say([string]$msg) { [Console]::Error.WriteLine("luau-lsp plugin: $msg") }
# Turns C:/a/b/../c and mixed separators into one native absolute path.
function Full([string]$p) { [System.IO.Path]::GetFullPath($p) }

$Root = Pick $env:CLAUDE_PLUGIN_ROOT (Split-Path -Parent $PSScriptRoot)
$Proj = Pick $env:CLAUDE_PROJECT_DIR (Get-Location).Path
$Home_ = Pick $env:USERPROFILE $HOME
$MiseData = Pick $env:MISE_DATA_DIR (Join-Path (Pick $env:LOCALAPPDATA "$Home_/.local/share") 'mise')
$AppData = Pick $env:APPDATA "$Home_/.config"

function First-File([string[]]$paths) {
    foreach ($p in $paths) { if (Test-Path -LiteralPath $p -PathType Leaf) { return $p } }
    return $null
}

function Runs([string]$exe) {
    Push-Location -LiteralPath $Proj
    try { $null = & $exe --version 2>$null; return ($LASTEXITCODE -eq 0) } catch { return $false } finally { Pop-Location }
}

$Found = New-Object System.Collections.ArrayList
function Add-Found([string]$ver, [string]$path) {
    if ($path) { [void]$Found.Add([pscustomobject]@{ V = [version]$ver; P = $path; I = $Found.Count }) }
}

function Scan-VersionDirs([string]$pattern, [string[]]$names) {
    foreach ($d in @(Get-ChildItem -Path $pattern -Directory -ErrorAction SilentlyContinue)) {
        if ($d.Name -notmatch $VerRe) { continue }
        Add-Found $d.Name (First-File @($names | ForEach-Object { Join-Path $d.FullName $_ }))
    }
}

function Scan-Stores {
    # [find:rokit]
    Scan-VersionDirs (Join-Path $Home_ '.rokit/tool-storage/*/luau-lsp/*') @('luau-lsp.exe', 'luau-lsp')
    # [find:aftman]
    Scan-VersionDirs (Join-Path $Home_ '.aftman/tool-storage/*/luau-lsp/*') @('luau-lsp.exe', 'luau-lsp')
    # [find:foreman] tools/<source key>-<version>.exe, the key ending in luau-lsp
    foreach ($f in @(Get-ChildItem -Path (Join-Path $Home_ '.foreman/tools/*luau-lsp-*') -File -ErrorAction SilentlyContinue)) {
        if ($f.Name -match 'luau-lsp-(\d+\.\d+\.\d+)(\.exe)?$') { Add-Found $Matches[1] $f.FullName }
    }
    # [find:mise] installs/<backend>-<owner>-luau-lsp/<version>/
    Scan-VersionDirs (Join-Path $MiseData 'installs/*luau-lsp/*') @('luau-lsp.exe', 'luau-lsp', 'bin/luau-lsp.exe', 'bin/luau-lsp')
    # [find:editor] VS Code, Insiders, Cursor, VS Code Server extensions: <id>-<version>[-<target>]/bin/server.exe
    foreach ($e in '.vscode', '.vscode-insiders', '.cursor', '.vscode-server') {
        foreach ($d in @(Get-ChildItem -Path (Join-Path $Home_ "$e/extensions/$ExtId-*") -Directory -ErrorAction SilentlyContinue)) {
            $v = ($d.Name.Substring($ExtId.Length + 1) -split '-')[0]
            if ($v -match $VerRe) { Add-Found $v (First-File @((Join-Path $d.FullName 'bin/server.exe'), (Join-Path $d.FullName 'bin/server'))) }
        }
    }
}

function Editor-File([string[]]$names) {
    foreach ($d in (Join-Path $AppData 'Code'), (Join-Path $AppData 'Code - Insiders'), (Join-Path $AppData 'Cursor'), (Join-Path $Home_ '.vscode-server/data')) {
        foreach ($n in $names) {
            $f = Join-Path $d "User/globalStorage/$ExtId/$n"
            if (Test-Path -LiteralPath $f -PathType Leaf) { return $f }
        }
    }
    return $null
}

function Find-Bin {
    # [find:env]
    if ($env:LUAU_LSP_BIN) {
        if (Test-Path -LiteralPath $env:LUAU_LSP_BIN -PathType Leaf) { return $env:LUAU_LSP_BIN }
        Say "LUAU_LSP_BIN=$env:LUAU_LSP_BIN is not an executable file."
        return $null
    }
    # [find:mise-pin] the shim fails with "No version is set" outside a pinned directory, so only real paths count
    $mise = Get-Command mise -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($mise) {
        Push-Location -LiteralPath $Proj
        # Select-Object -First would stop the pipeline early and leave $LASTEXITCODE unset, so index instead.
        try { $b = @(& $mise.Source which luau-lsp 2>$null)[0] } catch { $b = $null } finally { Pop-Location }
        if ($LASTEXITCODE -eq 0 -and $b -and $b -notmatch '[\\/]shims[\\/]' -and (Test-Path -LiteralPath $b -PathType Leaf)) { return $b }
    }
    # [find:path] rokit, aftman, foreman and mise put trampolines here that fail without a pin
    $c = Get-Command luau-lsp -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c -and (Runs $c.Source)) { return $c.Source }
    # [find:stores] highest version; on a tie the earlier store wins
    Scan-Stores
    $best = $Found | Sort-Object -Property @{ Expression = 'V'; Descending = $true }, @{ Expression = 'I'; Descending = $false } | Select-Object -First 1
    if ($best) { return $best.P }
    # [find:fail]
    Say 'luau-lsp not found. Install it (rokit add JohnnyMorganz/luau-lsp, mise use github:JohnnyMorganz/luau-lsp, or the release zip on PATH) or set LUAU_LSP_BIN; see the plugin README.'
    return $null
}

$bin = Find-Bin
if (-not $bin) { exit 127 }

$platform = $env:LUAU_LSP_PLATFORM
if (-not $platform) {
    $platform = 'standard'
    if ((Test-Path -LiteralPath (Join-Path $Proj 'sourcemap.json')) -or @(Get-ChildItem -Path (Join-Path $Proj '*.project.json') -File -ErrorAction SilentlyContinue).Count -gt 0) {
        $platform = 'roblox'
    }
}
if ($platform -ne 'standard' -and $platform -ne 'roblox') {
    Say "LUAU_LSP_PLATFORM must be standard or roblox, got '$platform'."
    exit 2
}

$fromEditor = $bin -match ('[\\/]extensions[\\/]' + [regex]::Escape($ExtId) + '-')

# Each path argument is quoted whole; luau-lsp's C runtime strips the quotes.
$argv = @('lsp', '--stdio', '--flag:LuauSolverV2=true', ('"--settings=' + (Full (Join-Path $Root "lsp-settings/$platform.json")) + '"'))
if ($platform -eq 'roblox') {
    $defs = $env:LUAU_LSP_DEFS
    if (-not $defs -and $fromEditor) { $defs = Editor-File @('globalTypes.PluginSecurity.d.luau', 'globalTypes.None.d.luau') }
    $defs = Pick $defs (Join-Path $Root 'definitions/globalTypes.d.luau')
    $argv += '"--definitions=@roblox=' + (Full $defs) + '"'
    $docs = Pick $env:LUAU_LSP_DOCS (Editor-File @('api-docs.json'))
} else {
    $docs = Pick $env:LUAU_LSP_DOCS (Editor-File @('luau-api-docs.json'))
}
if ($docs) { $argv += '"--docs=' + (Full $docs) + '"' }

Write-Output ('LLSP_BIN=' + (Full $bin))
Write-Output ('LLSP_ARGS=' + ($argv -join ' '))

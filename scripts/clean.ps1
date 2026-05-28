# scripts/clean.ps1

param(
    [string]$Root = "."
)

Write-Host "Cleaning Python project cache files..." -ForegroundColor Cyan

$ErrorActionPreference = "Continue"

# 不建议递归进入的目录
$ExcludeDirs = @(
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".idea",
    ".vscode"
)

# 需要删除的目录名
$TargetDirs = @(
    "__pycache__",
#     ".pytest_cache",
#     ".ruff_cache",
#     ".mypy_cache",
    ".coverage_cache",
    "htmlcov"
)

# 需要删除的文件匹配
$TargetFiles = @(
    "*.pyc",
    "*.pyo",
    ".coverage",
    "coverage.xml"
)

function Test-IsExcludedPath {
    param(
        [string]$Path
    )

    foreach ($dir in $ExcludeDirs) {
        if ($Path -match "(^|[\\/])$([regex]::Escape($dir))([\\/]|$)") {
            return $true
        }
    }

    return $false
}

function Remove-Safely {
    param(
        [string]$Path
    )

    try {
        Remove-Item -Path $Path -Recurse -Force -ErrorAction Stop
        Write-Host "Removed: $Path" -ForegroundColor DarkGray
    }
    catch {
        Write-Warning "Skip failed: $Path"
    }
}

# 清理目录
foreach ($target in $TargetDirs) {
    Get-ChildItem -Path $Root `
        -Recurse `
        -Directory `
        -Force `
        -Filter $target `
        -ErrorAction SilentlyContinue |
        Where-Object { -not (Test-IsExcludedPath $_.FullName) } |
        ForEach-Object {
            Remove-Safely $_.FullName
        }
}

# 清理文件
foreach ($pattern in $TargetFiles) {
    Get-ChildItem -Path $Root `
        -Recurse `
        -File `
        -Force `
        -Filter $pattern `
        -ErrorAction SilentlyContinue |
        Where-Object { -not (Test-IsExcludedPath $_.FullName) } |
        ForEach-Object {
            Remove-Safely $_.FullName
        }
}

Write-Host "Clean completed." -ForegroundColor Green

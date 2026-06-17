from __future__ import annotations

import fnmatch
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

# =========================
# 全局配置区
# =========================

# 项目根目录：如果脚本放在 scripts/pack_project.py，就用 parents[1]
# 项目根目录：当前脚本放在 scripts/zip_tools.py，所以取 parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 是否包含日期
WITH_DATE = False

# clean.ps1 路径
CLEAN_SCRIPT = PROJECT_ROOT / "scripts" / "clean.ps1"

# 打包输出目录
OUTPUT_DIR = PROJECT_ROOT / "dist"

# 压缩包名称前缀
ZIP_NAME_PREFIX = "JobPilot"

# 是否先执行 clean.ps1
RUN_CLEAN_SCRIPT = True

# Windows PowerShell 程序
POWERSHELL_EXE = "powershell.exe"

# 排除目录名：任意层级命中都会排除
EXCLUDE_DIR_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "build",
    "htmlcov",
    ".codex",
    "logs",
    "temp",
    "storage",
}

# 排除相对路径：相对于 PROJECT_ROOT，命中该路径及其子路径都会排除
EXCLUDE_RELATIVE_PATHS = {
    "docs/ai_report",
    "docs/八股文档",
    "docs/杂项",
    "front",
    "openspec",
    "scripts",
    ".github",
}

# 排除文件名
EXCLUDE_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.prod",
    ".env.test",
    ".coverage",
    "JobPilot.zip",
}

# 排除文件后缀
EXCLUDE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".sqlite",
    ".db",
}

# 排除文件通配符：匹配相对路径或文件名
EXCLUDE_GLOBS = {
    "*.zip",
    "JobPilot.zip",
}

# 是否打印加入压缩包的文件
VERBOSE = False

# =========================
# 脚本逻辑区
# =========================


def run_clean_script() -> None:
    """调用 clean.ps1 清理缓存。"""

    if not RUN_CLEAN_SCRIPT:
        print("[skip] RUN_CLEAN_SCRIPT = False")
        return

    if not CLEAN_SCRIPT.exists():
        print(f"[warn] clean.ps1 not found: {CLEAN_SCRIPT}")
        return

    print(f"[clean] running: {CLEAN_SCRIPT}")

    subprocess.run(
        [
            POWERSHELL_EXE,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(CLEAN_SCRIPT),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


def is_under_relative_path(relative_text: str, excluded: str) -> bool:
    excluded = excluded.strip("/").replace("\\", "/")
    return relative_text == excluded or relative_text.startswith(excluded + "/")


def is_excluded(path: Path) -> bool:
    """判断某个文件或目录是否应该被排除。"""

    relative_path = path.relative_to(PROJECT_ROOT)
    relative_text = relative_path.as_posix()

    for excluded in EXCLUDE_RELATIVE_PATHS:
        if is_under_relative_path(relative_text, excluded):
            return True

    for part in relative_path.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True

    if path.is_file():
        if path.name in EXCLUDE_FILE_NAMES:
            return True

        if path.suffix in EXCLUDE_FILE_SUFFIXES:
            return True

        for pattern in EXCLUDE_GLOBS:
            if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(relative_text, pattern):
                return True

    return False


def build_zip_path() -> Path:
    if WITH_DATE:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return OUTPUT_DIR / f"{ZIP_NAME_PREFIX}_{date_str}.zip"
    else:
        return OUTPUT_DIR / f"{ZIP_NAME_PREFIX}.zip"


def pack_project() -> Path:
    """打包项目目录。"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = build_zip_path()

    print(f"[pack] project root: {PROJECT_ROOT}")
    print(f"[pack] output: {zip_path}")

    file_count = 0

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for path in PROJECT_ROOT.rglob("*"):
            if path == zip_path:
                continue

            if is_excluded(path):
                continue

            if path.is_dir():
                continue

            arcname = path.relative_to(PROJECT_ROOT)

            if VERBOSE:
                print(f"[add] {arcname}")

            zip_file.write(path, arcname)
            file_count += 1

    print(f"[done] packed {file_count} files")
    print(f"[done] zip file: {zip_path}")

    return zip_path


def main() -> None:
    run_clean_script()
    pack_project()


if __name__ == "__main__":
    main()

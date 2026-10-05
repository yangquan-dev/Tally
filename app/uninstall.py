from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import (
    get_app_bundle_path,
    get_frozen_data_dir,
    get_install_dir,
    get_legacy_data_dir,
    is_frozen,
)


def _cleanup_app_support_dir() -> None:
    support = get_legacy_data_dir()
    if support.exists():
        shutil.rmtree(support, ignore_errors=True)


def uninstall_portable_app() -> None:
    """卸载打包版：删除数据目录与程序文件，然后退出进程。"""
    if not is_frozen():
        raise RuntimeError("仅打包版支持卸载")

    install_dir = get_install_dir().resolve()
    app_bundle = get_app_bundle_path()
    if app_bundle is not None:
        app_bundle = app_bundle.resolve()

    if sys.platform == "win32":
        _uninstall_windows(install_dir)
        return

    # macOS：删除 Application Support/Tally（含 data 与 bootstrap）以及 .app
    _cleanup_app_support_dir()
    if app_bundle is not None and app_bundle.exists():
        shutil.rmtree(app_bundle, ignore_errors=True)
    # 清理可能残留的旧版「.app 同级 data」
    sibling_data = install_dir / "data"
    if sibling_data.exists() and sibling_data.resolve() != get_frozen_data_dir().resolve():
        shutil.rmtree(sibling_data, ignore_errors=True)
    sys.exit(0)


def _is_safe_to_remove_directory(dir_path: Path) -> bool:
    """判断是否为安全的可整目录删除专属程序目录，绝不删除桌面、下载、盘符根目录等。"""
    try:
        resolved = dir_path.resolve()
        # 盘符根或系统根路径
        if resolved == resolved.parent:
            return False
        home = Path.home().resolve()
        if resolved == home:
            return False
        dangerous_names = {
            "desktop",
            "downloads",
            "documents",
            "pictures",
            "music",
            "videos",
            "桌面",
            "下载",
            "文档",
            "图片",
            "音乐",
            "视频",
            "windows",
            "program files",
            "program files (x86)",
            "appdata",
        }
        if resolved.name.lower() in dangerous_names:
            return False
        if resolved.parent == home and resolved.name.lower() in dangerous_names:
            return False
        # 必须是 Tally 专属目录名
        if resolved.name.lower() != "tally":
            return False
        return True
    except Exception:
        return False


def _uninstall_windows(install_dir: Path) -> None:
    """通过临时 bat 在进程退出后安全清理程序文件，避免误删非专属目录。"""
    _cleanup_app_support_dir()

    bat_path = Path(tempfile.gettempdir()) / f"tally_uninstall_{os.getpid()}.bat"
    lines = [
        "@echo off",
        "ping 127.0.0.1 -n 3 >nul",
        f'del /f /q "{install_dir}\\Tally.exe" 2>nul',
        f'rd /s /q "{install_dir}\\_internal" 2>nul',
        f'rd /s /q "{install_dir}\\data" 2>nul',
        f'del /f /q "{install_dir}\\使用说明.txt" 2>nul',
        f'del /f /q "{install_dir}\\*.lic" 2>nul',
        'rd /s /q "%APPDATA%\\Tally" 2>nul',
    ]
    if _is_safe_to_remove_directory(install_dir):
        lines.append(f'rd /s /q "{install_dir}" 2>nul')
    lines.extend([
        'del "%~f0"',
        "",
    ])

    bat_path.write_text(
        "\r\n".join(lines),
        encoding="gbk",
        errors="replace",
    )

    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags |= subprocess.CREATE_NO_WINDOW
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creationflags |= subprocess.DETACHED_PROCESS

    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        creationflags=creationflags,
        close_fds=True,
    )
    sys.exit(0)


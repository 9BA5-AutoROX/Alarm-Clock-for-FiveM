"""
Path Resolution Module
======================
Resolves file paths correctly for both development and PyInstaller-packaged modes.
"""

import sys
from pathlib import Path


def get_base_path() -> Path:
    """
    Return the base directory of the application.
    
    - Dev mode:     the project root (where main.py lives)
    - PyInstaller:  the directory containing the .exe (--onedir)
    """
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        return Path(sys.executable).parent
    else:
        # Running as a normal script
        return Path(__file__).parent.parent


def resolve(relative_path: str) -> Path:
    """
    Resolve a project-relative path to an absolute path.
    
    Args:
        relative_path: e.g. "presets/alarm_presets.json"
    
    Returns:
        Absolute Path object.
    """
    return get_base_path() / relative_path

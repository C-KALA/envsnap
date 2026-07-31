# replay.py — restores a saved environment snapshot by reinstalling packages and verifying environment state.

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Any

from .capture import (
    get_python_version,
    get_pip_version,
    get_docker_version,
    get_docker_compose_version
)

SYSTEM_PACKAGES = {
    "apt-listchanges", "python-apt", "python-debian", "cupshelpers", 
    "dbus-python", "pycairo", "PyGObject", "Brlapi", "reportbug"
}

def check_prerequisites() -> dict[str, dict[str, Any]]:
    """
    Checks what tools are available on the current machine (python, pip, docker, docker compose).
    Returns a dict with availability and version for each tool.
    """
    py_ver = get_python_version()
    pip_ver = get_pip_version()
    docker_ver = get_docker_version()
    compose_ver = get_docker_compose_version()
    
    return {
        "python": {"available": py_ver is not None, "version": py_ver},
        "pip": {"available": pip_ver is not None, "version": pip_ver},
        "docker": {"available": docker_ver is not None, "version": docker_ver},
        "docker_compose": {"available": compose_ver is not None, "version": compose_ver},
    }

def verify_env_keys(snapshot: dict[str, Any], project_root: Path | None = None) -> dict[str, Any]:
    """
    Reads required env keys from the snapshot and checks if they exist in the current .env file.
    Returns missing keys, present keys, and whether the .env file exists.
    """
    root = project_root if project_root else Path.cwd()
    required_keys = snapshot.get("env_keys") or []
    env_file = root / ".env"
    
    has_env_file = env_file.is_file()
    present = []
    missing = []
    
    if not has_env_file:
        missing = list(required_keys)
    else:
        current_keys = set()
        try:
            with env_file.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    if "=" in stripped:
                        key = stripped.split("=", 1)[0].strip()
                        if key:
                            current_keys.add(key)
        except Exception:
            pass
            
        for k in required_keys:
            if k in current_keys:
                present.append(k)
            else:
                missing.append(k)
                
    return {
        "missing": missing,
        "present": present,
        "has_env_file": has_env_file
    }

def install_packages(snapshot: dict[str, Any]) -> dict[str, list[str]]:
    """
    Installs packages from the snapshot using pip via subprocess.
    Filters out system packages that should not be pip-installed.
    Returns lists of installed, failed, and skipped packages.
    """
    packages = snapshot.get("installed_packages") or {}
    installed = []
    failed = []
    skipped = []
    
    for pkg, version in packages.items():
        if pkg in SYSTEM_PACKAGES:
            skipped.append(pkg)
            continue
            
        if version:
            req = f"{pkg}=={version}"
        else:
            req = pkg
            
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", req, "--break-system-packages"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                installed.append(pkg)
            else:
                failed.append(pkg)
        except Exception:
            failed.append(pkg)
            
    return {
        "installed": installed,
        "failed": failed,
        "skipped": skipped
    }

def replay_environment(snapshot: dict[str, Any], project_root: Path) -> dict[str, Any]:
    """
    Runs full replay: checks prerequisites, verifies env keys, and installs packages.
    Returns a full report containing the results of each step.
    """
    prereqs = check_prerequisites()
    env_report = verify_env_keys(snapshot, project_root)
    pkg_report = install_packages(snapshot)
    
    return {
        "prerequisites": prereqs,
        "env_keys": env_report,
        "packages": pkg_report
    }

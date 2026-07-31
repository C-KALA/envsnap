# capture.py — responsible for probing the current environment: Python version,
# installed packages, environment variables, OS info, active services, and open ports.

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import psutil

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> str | None:
    """Run *cmd* in a subprocess and return stripped stdout, or None on failure.

    Errors (missing binary, non-zero exit, timeout) are silently swallowed so
    that a missing tool never causes capture to abort.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


# ---------------------------------------------------------------------------
# Individual capture functions
# ---------------------------------------------------------------------------

def get_python_version() -> str | None:
    """Return the current Python version string (e.g. '3.11.4').

    Uses :mod:`sys` so no subprocess overhead is needed.
    Returns ``None`` if the version cannot be determined (should never happen).
    """
    try:
        info = sys.version_info
        return f"{info.major}.{info.minor}.{info.micro}"
    except Exception:
        return None


def get_pip_version() -> str | None:
    """Return the installed pip version string by running ``pip --version``.

    Returns ``None`` if pip is not found or the version cannot be parsed.
    """
    output = _run([sys.executable, "-m", "pip", "--version"])
    if output is None:
        return None
    # e.g. "pip 23.2.1 from /usr/lib/python3/dist-packages/pip (python 3.11)"
    try:
        return output.split()[1]
    except IndexError:
        return None


def get_docker_version() -> str | None:
    """Return the installed Docker Engine version by running ``docker --version``.

    Returns ``None`` if Docker is not installed or not accessible.
    """
    output = _run(["docker", "--version"])
    if output is None:
        return None
    # e.g. "Docker version 24.0.5, build ced0996"
    try:
        return output.split("version")[1].split(",")[0].strip()
    except (IndexError, AttributeError):
        return output  # fallback: return the raw string


def get_docker_compose_version() -> str | None:
    """Return the Docker Compose version by running ``docker compose version``.

    Tries the modern plugin (``docker compose``) first, then falls back to the
    legacy standalone binary (``docker-compose``).
    Returns ``None`` if neither variant is present.
    """
    # Modern plugin: docker compose version
    output = _run(["docker", "compose", "version"])
    if output:
        # e.g. "Docker Compose version v2.20.2"
        try:
            return output.split("version")[-1].strip().lstrip("v")
        except (IndexError, AttributeError):
            return output

    # Legacy standalone
    output = _run(["docker-compose", "--version"])
    if output:
        try:
            return output.split("version")[-1].split(",")[0].strip().lstrip("v")
        except (IndexError, AttributeError):
            return output

    return None


def get_docker_compose_info(cwd: str | None = None) -> dict[str, Any] | None:
    """Parse ``docker-compose.yml`` (or ``docker-compose.yaml``) in *cwd*.

    Extracts:
    - ``services``: list of service names
    - ``ports``: mapping of service → list of port strings
    - ``depends_on``: mapping of service → list of dependency names
    - ``images``: mapping of service → image name
    - ``volumes``: list of top-level named volumes

    Returns ``None`` if no compose file is found, PyYAML is unavailable, or
    the file cannot be parsed.
    """
    if not _YAML_AVAILABLE:
        return None

    base = Path(cwd) if cwd else Path.cwd()
    compose_file: Path | None = None
    for name in ("docker-compose.yml", "docker-compose.yaml",
                 "compose.yml", "compose.yaml"):
        candidate = base / name
        if candidate.is_file():
            compose_file = candidate
            break

    if compose_file is None:
        return None

    try:
        with compose_file.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    services_raw: dict = data.get("services") or {}
    services: list[str] = list(services_raw.keys())

    ports: dict[str, list[str]] = {}
    depends_on: dict[str, list[str]] = {}
    images: dict[str, str | None] = {}

    for svc, cfg in services_raw.items():
        if not isinstance(cfg, dict):
            continue

        # ports
        raw_ports = cfg.get("ports") or []
        ports[svc] = [str(p) for p in raw_ports]

        # depends_on — may be a list or a dict (long form)
        raw_deps = cfg.get("depends_on") or []
        if isinstance(raw_deps, dict):
            depends_on[svc] = list(raw_deps.keys())
        elif isinstance(raw_deps, list):
            depends_on[svc] = raw_deps
        else:
            depends_on[svc] = []

        # image
        images[svc] = cfg.get("image")

    # Top-level named volumes
    volumes_raw: dict = data.get("volumes") or {}
    volumes: list[str] = list(volumes_raw.keys())

    return {
        "file": str(compose_file),
        "services": services,
        "ports": ports,
        "depends_on": depends_on,
        "images": images,
        "volumes": volumes,
    }


def get_env_keys(cwd: str | None = None) -> list[str] | None:
    """Read the ``.env`` file in *cwd* and return only the variable **keys**.

    Values are intentionally excluded to avoid capturing secrets in snapshots.
    Lines starting with ``#`` and blank lines are ignored.
    Returns ``None`` if no ``.env`` file is found.
    """
    base = Path(cwd) if cwd else Path.cwd()
    env_file = base / ".env"
    if not env_file.is_file():
        return None

    keys: list[str] = []
    try:
        with env_file.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key:
                        keys.append(key)
    except Exception:
        return None

    return keys


def get_installed_packages() -> dict[str, str] | None:
    """Return all packages visible to the current Python interpreter via ``pip freeze``.

    Returns a dict mapping package name → version string.
    Returns ``None`` if pip freeze fails entirely.
    """
    output = _run([sys.executable, "-m", "pip", "freeze"])
    if output is None:
        return None

    packages: dict[str, str] = {}
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if "==" in line:
            name, _, version = line.partition("==")
            packages[name.strip()] = version.strip()
        else:
            # editable installs or VCS refs — store as-is under key
            packages[line] = ""

    return packages


def get_open_ports() -> list[dict[str, Any]] | None:
    """Return all TCP/UDP ports currently bound on localhost using :mod:`psutil`.

    Each entry is a dict with keys:
    - ``port``: int
    - ``proto``: ``"tcp"`` or ``"udp"``
    - ``status``: connection status string (e.g. ``"LISTEN"``)
    - ``pid``: int or None
    - ``process``: process name string or None

    Returns ``None`` if psutil is unavailable or raises an unexpected error.
    """
    try:
        seen: set[tuple] = set()
        results: list[dict[str, Any]] = []

        for conn in psutil.net_connections(kind="inet"):
            laddr = conn.laddr
            if not laddr:
                continue
            if laddr.ip not in ("0.0.0.0", "::", "127.0.0.1", "::1", ""):
                # Only include ports bound to all interfaces or localhost
                pass  # still include — admins may bind to a specific IP

            key = (conn.type, laddr.port)
            if key in seen:
                continue
            seen.add(key)

            proto = "tcp" if conn.type == psutil._common.socket.SOCK_STREAM else "udp"

            # Resolve PID → process name safely
            process_name: str | None = None
            pid: int | None = conn.pid
            if pid:
                try:
                    process_name = psutil.Process(pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            results.append({
                "port": laddr.port,
                "proto": proto,
                "status": conn.status if conn.status else None,
                "pid": pid,
                "process": process_name,
            })

        results.sort(key=lambda x: x["port"])
        return results
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Primary public API
# ---------------------------------------------------------------------------

def capture_environment(cwd: str | None = None) -> dict[str, Any]:
    """Capture a full snapshot of the current development environment.

    Collects:
    - Python and pip versions
    - Docker and Docker Compose versions
    - Parsed ``docker-compose.yml`` metadata
    - ``.env`` variable keys (values omitted for security)
    - All installed Python packages (``pip freeze``)
    - Open/listening ports on the host

    Parameters
    ----------
    cwd:
        Directory to search for ``docker-compose.yml`` and ``.env``.
        Defaults to the current working directory.

    Returns
    -------
    dict
        A dictionary containing all captured fields. Missing or unavailable
        data is represented as ``None`` — the function never raises.
    """
    return {
        "python_version": get_python_version(),
        "pip_version": get_pip_version(),
        "docker_version": get_docker_version(),
        "docker_compose_version": get_docker_compose_version(),
        "docker_compose": get_docker_compose_info(cwd),
        "env_keys": get_env_keys(cwd),
        "installed_packages": get_installed_packages(),
        "open_ports": get_open_ports(),
    }

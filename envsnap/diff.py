# diff.py — compares two environment snapshots and produces a human-readable diff highlighting additions, removals, and changes across all tracked fields.

from typing import Any

def diff_snapshots(snapshot_a: dict[str, Any], snapshot_b: dict[str, Any]) -> dict[str, Any]:
    """
    Compares two snapshot dictionaries and returns a diff dictionary highlighting
    additions, removals, and changes in runtime, packages, services, ports, and env keys.
    Handles missing keys gracefully.
    """
    if not isinstance(snapshot_a, dict):
        snapshot_a = {}
    if not isinstance(snapshot_b, dict):
        snapshot_b = {}

    diff: dict[str, Any] = {
        "runtime_changes": {
            "python": None,
            "pip": None,
            "docker": None,
            "docker_compose": None,
        },
        "packages": {
            "added": {},
            "removed": {},
            "changed": {},
        },
        "services": {
            "added": [],
            "removed": [],
        },
        "ports": {
            "added": [],
            "removed": [],
        },
        "env_keys": {
            "added": [],
            "removed": [],
        },
    }

    # Runtime changes
    for our_key, snap_key in [
        ("python", "python_version"),
        ("pip", "pip_version"),
        ("docker", "docker_version"),
        ("docker_compose", "docker_compose_version")
    ]:
        val_a = snapshot_a.get(snap_key)
        val_b = snapshot_b.get(snap_key)
        if val_a != val_b:
            diff["runtime_changes"][our_key] = {"from": val_a, "to": val_b}

    # Packages
    pkg_a = snapshot_a.get("installed_packages") or {}
    pkg_b = snapshot_b.get("installed_packages") or {}
    
    for p, v in pkg_b.items():
        if p not in pkg_a:
            diff["packages"]["added"][p] = v
        elif pkg_a[p] != v:
            diff["packages"]["changed"][p] = {"from": pkg_a[p], "to": v}
            
    for p, v in pkg_a.items():
        if p not in pkg_b:
            diff["packages"]["removed"][p] = v

    # Services
    dc_a = snapshot_a.get("docker_compose") or {}
    dc_b = snapshot_b.get("docker_compose") or {}
    
    srv_a = set(dc_a.get("services", []) or [])
    srv_b = set(dc_b.get("services", []) or [])
    
    diff["services"]["added"] = sorted(list(srv_b - srv_a))
    diff["services"]["removed"] = sorted(list(srv_a - srv_b))

    # Ports - Extracting just the port numbers
    ports_a_list = snapshot_a.get("open_ports") or []
    ports_b_list = snapshot_b.get("open_ports") or []
    
    p_a = set(str(p.get("port")) for p in ports_a_list if isinstance(p, dict) and p.get("port"))
    p_b = set(str(p.get("port")) for p in ports_b_list if isinstance(p, dict) and p.get("port"))
    
    diff["ports"]["added"] = sorted(list(p_b - p_a), key=lambda x: int(x) if x.isdigit() else x)
    diff["ports"]["removed"] = sorted(list(p_a - p_b), key=lambda x: int(x) if x.isdigit() else x)

    # Env keys
    env_a = set(snapshot_a.get("env_keys") or [])
    env_b = set(snapshot_b.get("env_keys") or [])
    
    diff["env_keys"]["added"] = sorted(list(env_b - env_a))
    diff["env_keys"]["removed"] = sorted(list(env_a - env_b))

    return diff

def has_changes(diff: dict[str, Any]) -> bool:
    """
    Returns True if any section in the diff dictionary has actual changes,
    False otherwise.
    """
    if not isinstance(diff, dict):
        return False
        
    for val in diff.get("runtime_changes", {}).values():
        if val is not None:
            return True
            
    for val in diff.get("packages", {}).values():
        if val:  # dict has items
            return True
            
    for val in diff.get("services", {}).values():
        if val:  # list has items
            return True
            
    for val in diff.get("ports", {}).values():
        if val:
            return True
            
    for val in diff.get("env_keys", {}).values():
        if val:
            return True
            
    return False

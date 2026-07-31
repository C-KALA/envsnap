# cli.py — entry point for the envsnap CLI; defines the `main` Click command group and all sub-commands (init, capture, log).

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .capture import capture_environment
from .snapshot import save_snapshot, list_snapshots, load_snapshot
from .diff import diff_snapshots, has_changes

console = Console()

@click.group()
def main():
    """envsnap - Capture, version and replay your dev environment like Git."""
    pass

@main.command()
def init():
    """Initialise a new envsnap repository in the current directory."""
    try:
        project_root = Path.cwd()
        envsnap_dir = project_root / ".envsnap"
        
        if envsnap_dir.exists():
            console.print("[yellow]Warning: .envsnap already exists in this directory.[/yellow]")
            return
            
        snapshots_dir = envsnap_dir / "snapshots"
        snapshots_dir.mkdir(parents=True)
        
        current_snapshot = envsnap_dir / "current.snapshot"
        with current_snapshot.open("w", encoding="utf-8") as f:
            json.dump({}, f)
            
        console.print("[green]Success: Initialised empty envsnap repository in .envsnap/[/green]")
    except Exception as e:
        console.print(f"[red]Error initialising repository: {str(e)}[/red]")

@main.command()
@click.option("--json", "json_output", is_flag=True, help="Output raw JSON instead of a table.")
def capture(json_output: bool):
    """Capture the current environment and save a new snapshot."""
    try:
        project_root = Path.cwd()
        envsnap_dir = project_root / ".envsnap"
        
        if not envsnap_dir.exists():
            console.print("[red]Error: Not an envsnap repository. Run 'envsnap init' first.[/red]")
            return
            
        with console.status("Capturing environment..."):
            data = capture_environment(str(project_root))
            saved_path = save_snapshot(data, project_root)
            
        if not saved_path:
            console.print("[red]Error: Failed to save snapshot.[/red]")
            return
            
        if json_output:
            console.print_json(data=data)
            return
            
        table = Table(title="Captured Environment Summary")
        table.add_column("Component", style="cyan")
        table.add_column("Details", style="magenta")
        
        table.add_row("Python", str(data.get("python_version") or "Not found"))
        table.add_row("Pip", str(data.get("pip_version") or "Not found"))
        table.add_row("Docker", str(data.get("docker_version") or "Not found"))
        table.add_row("Docker Compose", str(data.get("docker_compose_version") or "Not found"))
        
        packages = data.get("installed_packages") or {}
        table.add_row("Installed Packages", str(len(packages)))
        
        compose_info = data.get("docker_compose")
        services_count = len(compose_info.get("services", [])) if compose_info else 0
        table.add_row("Docker Services", str(services_count))
        
        ports = data.get("open_ports") or []
        table.add_row("Open Ports", str(len(ports)))
        
        env_keys = data.get("env_keys") or []
        table.add_row("Env Variables (.env)", str(len(env_keys)))
        
        console.print(table)
        console.print(f"[green]Snapshot saved to: {saved_path}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error during capture: {str(e)}[/red]")

@main.command()
@click.option("--json", "json_output", is_flag=True, help="Output raw JSON instead of a list.")
def log(json_output: bool):
    """List all saved environment snapshots."""
    try:
        project_root = Path.cwd()
        envsnap_dir = project_root / ".envsnap"
        
        if not envsnap_dir.exists():
            console.print("[red]Error: Not an envsnap repository. Run 'envsnap init' first.[/red]")
            return
            
        snapshots = list_snapshots(project_root)
        
        if not snapshots:
            console.print("[yellow]No snapshots found.[/yellow]")
            return
            
        if json_output:
            json_list = []
            for s in snapshots:
                json_list.append({
                    "filename": s["filename"],
                    "timestamp": s["timestamp"].isoformat(),
                    "full_path": s["full_path"]
                })
            console.print_json(data=json_list)
            return
            
        table = Table(title="Environment Snapshots")
        table.add_column("No.", style="dim")
        table.add_column("Timestamp", style="cyan")
        table.add_column("Python", style="green")
        table.add_column("Docker", style="blue")
        table.add_column("Services", style="yellow")
        table.add_column("Status", style="magenta")
        
        for idx, snap in enumerate(snapshots, start=1):
            data = load_snapshot(Path(snap["full_path"])) or {}
            
            ts_str = snap["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            py_ver = str(data.get("python_version") or "-")
            docker_ver = str(data.get("docker_version") or "-")
            
            compose_info = data.get("docker_compose")
            services_count = str(len(compose_info.get("services", []))) if compose_info else "0"
            
            status = "[bold green]Current[/bold green]" if idx == 1 else ""
            
            table.add_row(str(idx), ts_str, py_ver, docker_ver, services_count, status)
            
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error retrieving log: {str(e)}[/red]")

@main.command()
@click.argument("snapshot1", required=False)
@click.argument("snapshot2", required=False)
@click.option("--json", "json_output", is_flag=True, help="Output raw JSON instead of a table.")
def diff(snapshot1: str | None, snapshot2: str | None, json_output: bool):
    """Compare two snapshots and show what changed."""
    try:
        project_root = Path.cwd()
        envsnap_dir = project_root / ".envsnap"
        
        if not envsnap_dir.exists():
            console.print("[red]Error: Not an envsnap repository. Run 'envsnap init' first.[/red]")
            return
            
        snapshots = list_snapshots(project_root)
        if not snapshots:
            console.print("[yellow]No snapshots found to diff.[/yellow]")
            return
            
        snap1_path = None
        snap2_path = None
        
        if not snapshot1 and not snapshot2:
            if len(snapshots) < 2:
                console.print("[yellow]Need at least two snapshots to diff.[/yellow]")
                return
            snap1_path = snapshots[1]["full_path"]
            snap2_path = snapshots[0]["full_path"]
        elif snapshot1 and not snapshot2:
            snap1_path = snapshot1
            snap2_path = snapshots[0]["full_path"]
        elif snapshot1 and snapshot2:
            snap1_path = snapshot1
            snap2_path = snapshot2
            
        def resolve_snap(path_str):
            p = Path(path_str)
            if p.is_absolute() and p.exists():
                return p
            p_in_dir = envsnap_dir / "snapshots" / path_str
            if p_in_dir.exists():
                return p_in_dir
            if not path_str.endswith(".snapshot"):
                p_in_dir = envsnap_dir / "snapshots" / f"{path_str}.snapshot"
                if p_in_dir.exists():
                    return p_in_dir
            return p
            
        s1_path = resolve_snap(snap1_path)
        s2_path = resolve_snap(snap2_path)
        
        data1 = load_snapshot(s1_path)
        data2 = load_snapshot(s2_path)
        
        if data1 is None:
            console.print(f"[red]Error: Could not load snapshot {snap1_path}[/red]")
            return
        if data2 is None:
            console.print(f"[red]Error: Could not load snapshot {snap2_path}[/red]")
            return
            
        diff_data = diff_snapshots(data1, data2)
        
        if json_output:
            console.print_json(data=diff_data)
            return
            
        if not has_changes(diff_data):
            console.print("[green]No changes detected between snapshots.[/green]")
            return
            
        console.print(f"Diffing: [dim]{s1_path.name}[/dim] -> [dim]{s2_path.name}[/dim]\n")
        
        if any(v is not None for v in diff_data["runtime_changes"].values()):
            table = Table(title="Runtime Changes", title_justify="left")
            table.add_column("Component", style="cyan")
            table.add_column("Old", style="red")
            table.add_column("New", style="green")
            for k, v in diff_data["runtime_changes"].items():
                if v:
                    table.add_row(k, str(v.get("from") or "-"), str(v.get("to") or "-"))
            console.print(table)
            console.print()
            
        pkg = diff_data["packages"]
        if pkg["added"] or pkg["removed"] or pkg["changed"]:
            table = Table(title="Package Changes", title_justify="left")
            table.add_column("Status", style="bold")
            table.add_column("Package")
            table.add_column("Details")
            for p, v in pkg["added"].items():
                table.add_row("[green]+ Added[/green]", p, v)
            for p, v in pkg["removed"].items():
                table.add_row("[red]- Removed[/red]", p, v)
            for p, v in pkg["changed"].items():
                table.add_row("[yellow]~ Changed[/yellow]", p, f"{v['from']} -> {v['to']}")
            console.print(table)
            console.print()
            
        srv = diff_data["services"]
        if srv["added"] or srv["removed"]:
            table = Table(title="Docker Services", title_justify="left")
            table.add_column("Status", style="bold")
            table.add_column("Service")
            for s in srv["added"]:
                table.add_row("[green]+ Added[/green]", s)
            for s in srv["removed"]:
                table.add_row("[red]- Removed[/red]", s)
            console.print(table)
            console.print()
            
        ports = diff_data["ports"]
        if ports["added"] or ports["removed"]:
            table = Table(title="Open Ports", title_justify="left")
            table.add_column("Status", style="bold")
            table.add_column("Port")
            for p in ports["added"]:
                table.add_row("[green]+ Added[/green]", str(p))
            for p in ports["removed"]:
                table.add_row("[red]- Removed[/red]", str(p))
            console.print(table)
            console.print()
            
        envs = diff_data["env_keys"]
        if envs["added"] or envs["removed"]:
            table = Table(title="Environment Variables (.env)", title_justify="left")
            table.add_column("Status", style="bold")
            table.add_column("Key")
            for k in envs["added"]:
                table.add_row("[green]+ Added[/green]", k)
            for k in envs["removed"]:
                table.add_row("[red]- Removed[/red]", k)
            console.print(table)
            console.print()
            
    except Exception as e:
        console.print(f"[red]Error diffing snapshots: {str(e)}[/red]")

if __name__ == "__main__":
    main()

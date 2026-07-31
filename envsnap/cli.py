# cli.py — entry point for the envsnap CLI; defines the `main` Click command group and all sub-commands (init, capture, log).

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .capture import capture_environment
from .snapshot import save_snapshot, list_snapshots, load_snapshot

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

if __name__ == "__main__":
    main()



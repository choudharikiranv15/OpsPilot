import typer
from rich.console import Console
from pathlib import Path

from opspilot.state import AgentState
from opspilot.config import load_config

app = typer.Typer(help="OpsPilot - Agentic AI CLI for incident analysis")
console = Console()


@app.callback()
def main():
    """
    OpsPilot CLI entry point.
    """
    pass


@app.command()
def analyze():
    """
    Analyze the current project for runtime issues.
    """
    project_root = str(Path.cwd())

    state = AgentState(project_root=project_root)
    config = load_config(project_root)

    console.print("[bold green]✔ OpsPilot initialized[/bold green]")
    console.print(
        f"[bold green]✔ Project detected[/bold green]: {project_root}")
    console.print(f"Config loaded: {bool(config)}")

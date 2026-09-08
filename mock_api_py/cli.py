"""Command-line interface (Typer + Rich) for mock-api-py."""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 encoding on Windows terminal
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from mock_api_py import __version__
from mock_api_py.generator import generate_mock_database
from mock_api_py.server import create_app
from mock_api_py.store import DataStore

app = typer.Typer(
    name="mock-api",
    help="Instant Modern Mock REST API Engine for Developers",
    add_completion=False,
)
console = Console(force_terminal=True)


def find_available_port(host: str, start_port: int, max_attempts: int = 20) -> int:
    """Finds the first available TCP port starting from start_port."""
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    return start_port


def print_banner(
    host: str,
    port: int,
    store: DataStore,
    delay: Optional[str] = None,
    error_rate: float = 0.0,
    save: bool = False,
    read_only: bool = False,
    watch: bool = False,
    static_dir: Optional[str] = None,
    auth: bool = False,
    routes: Optional[str] = None,
) -> None:
    """Renders the aesthetic Rich startup banner and resource overview."""
    banner_text = Text()
    banner_text.append(f"⚡ mock-api v{__version__} ⚡\n", style="bold yellow")
    banner_text.append("Modern Instant Mock CRUD Server for Developers", style="cyan")

    panel = Panel(
        banner_text,
        border_style="bright_blue",
        expand=False,
        padding=(0, 4),
    )
    console.print()
    console.print(panel)

    base_url = f"http://{host}:{port}"
    console.print(f" 🚀 [bold green]Server running at:[/bold green]      [underline cyan]{base_url}[/underline cyan]")
    console.print(f" 💻 [bold cyan]Web Dashboard Studio:[/bold cyan]    [underline cyan]{base_url}/_admin[/underline cyan]")
    console.print(f" 📖 [bold magenta]Interactive API Docs:[/bold magenta]     [underline cyan]{base_url}/docs[/underline cyan]")
    console.print(f" 📘 [bold blue]TypeScript Definitions:[/bold blue]   [underline cyan]{base_url}/_types[/underline cyan]")
    console.print(f" 📤 [bold green]File Upload Endpoint:[/bold green]     [underline cyan]{base_url}/upload[/underline cyan]")

    status_parts = []
    if delay:
        status_parts.append(f"⏱️  Simulated Delay: [bold yellow]{delay}[/bold yellow]")
    if error_rate > 0:
        status_parts.append(f"🎲 Chaos Error Rate: [bold red]{int(error_rate * 100)}%[/bold red]")
    if watch:
        status_parts.append("👀 Watch: [bold green]ON[/bold green]")
    if auth:
        status_parts.append("🛡️  Auth: [bold green]JWT Active[/bold green]")
    if read_only:
        status_parts.append("🔒 Mode: [bold red]Read-Only[/bold red]")
    else:
        status_parts.append(f"💾 Auto-save: [bold green]{'ON' if save else 'OFF (In-Memory)'}[/bold green]")

    console.print(f" {' | '.join(status_parts)}")
    if routes:
        console.print(f" 🔀 [bold]Custom Routes:[/bold] [yellow]{routes}[/yellow]")
    if static_dir:
        console.print(f" 📁 [bold]Static files:[/bold]  [underline cyan]{base_url}/static[/underline cyan] [dim]({static_dir})[/dim]")
    console.print(" 📦 [bold]Detected Resources:[/bold]")

    collections = store.get_collections()
    for col_name, count in collections.items():
        console.print(f"   [dim]•[/dim] [bold cyan]GET[/bold cyan] [white]/{col_name:<14}[/white] [dim][{count} items][/dim]")

    singletons = store.get_singletons()
    for sin_name in singletons:
        console.print(f"   [dim]•[/dim] [bold cyan]GET[/bold cyan] [white]/{sin_name:<14}[/white] [dim][1 object][/dim]")

    console.print()


KNOWN_COMMANDS = {"generate", "run", "--help", "-h", "--version", "-v"}


@app.command(name="run")
def run_server(
    db_file: Optional[str] = typer.Argument(
        None,
        help="Path to the JSON database file. Defaults to db.json or sample_db.json if exists.",
    ),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host address."),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port."),
    delay: Optional[str] = typer.Option(
        None, "--delay", "-d", help="Simulated latency in ms (e.g. 500 or 200-800)."
    ),
    error_rate: float = typer.Option(
        0.0, "--error-rate", "-e", help="Random 500 error injection rate (0.0 - 1.0)."
    ),
    save: bool = typer.Option(
        False, "--save", "--write-back", help="Persist changes back to the JSON file on disk."
    ),
    read_only: bool = typer.Option(
        False, "--read-only", help="Block mutations (POST/PUT/PATCH/DELETE)."
    ),
    watch: bool = typer.Option(
        False, "--watch", "-w", help="Watch JSON file and auto-reload in-memory data on external change."
    ),
    static: Optional[str] = typer.Option(
        None, "--static", help="Directory path to serve static files from at /static."
    ),
    auth: bool = typer.Option(
        False, "--auth", help="Enable mock authentication and JWT token validation."
    ),
    routes: Optional[str] = typer.Option(
        None, "--routes", "-r", help="Path to JSON custom routes rewriter file."
    ),
) -> None:
    """Starts the instant modern mock REST API server from a JSON database file."""
    # Determine file path
    target_path: Optional[Path] = None
    if db_file:
        target_path = Path(db_file)
    elif Path("db.json").exists():
        target_path = Path("db.json")
    elif Path("sample_db.json").exists():
        target_path = Path("sample_db.json")

    initial_data = None
    if not target_path or not target_path.exists():
        if target_path:
            console.print(f"[bold red]Error:[/bold red] File '{target_path}' not found.")
            console.print("[dim]Tip: Run 'mock-api generate --output db.json' to create one.[/dim]")
            raise typer.Exit(code=1)
        else:
            # Create a minimal sample in-memory if no file provided
            console.print("[yellow]No JSON file specified. Using in-memory starter database...[/yellow]")
            initial_data = {
                "posts": [
                    {"id": 1, "title": "Hello World", "userId": 1},
                    {"id": 2, "title": "Modern Mock API", "userId": 1},
                ],
                "users": [
                    {"id": 1, "name": "Developer", "email": "dev@example.com"}
                ],
                "profile": {"status": "ready"}
            }

    store = DataStore(
        file_path=target_path,
        initial_data=initial_data,
        auto_save=save,
        read_only=read_only,
    )

    fastapi_app = create_app(
        store=store,
        delay=delay,
        error_rate=error_rate,
        enable_logging=True,
        watch=watch,
        static_dir=static,
        enable_auth=auth,
        routes_file=routes,
    )

    # Auto-switch to available port if port is busy
    actual_port = find_available_port(host, port)
    if actual_port != port:
        console.print(
            f"⚠️  [bold yellow]Port {port} is busy.[/bold yellow] "
            f"[bold green]Auto-switched to available port {actual_port}.[/bold green]\n"
        )

    print_banner(
        host=host,
        port=actual_port,
        store=store,
        delay=delay,
        error_rate=error_rate,
        save=save,
        read_only=read_only,
        watch=watch,
        static_dir=static,
        auth=auth,
        routes=routes,
    )

    uvicorn.run(
        fastapi_app,
        host=host,
        port=actual_port,
        log_level="warning",
        access_log=False,
    )


@app.command(name="generate")
def generate_command(
    output: str = typer.Option(
        "db.json", "--output", "-o", help="Target JSON file path."
    ),
    schema: str = typer.Option(
        "users:10,products:25,posts:50",
        "--schema",
        "-s",
        help="Comma-separated entity:count schema definitions.",
    ),
) -> None:
    """Generates a realistic synthetic JSON database using Faker."""
    console.print(f"[cyan]Generating synthetic database with schema:[/cyan] [yellow]{schema}[/yellow]...")
    db = generate_mock_database(schema_str=schema, output_path=output)
    total_records = sum(len(v) for v in db.values() if isinstance(v, list))
    console.print(
        f"✅ [bold green]Successfully generated[/bold green] [bold white]{output}[/bold white] "
        f"with [bold cyan]{total_records}[/bold cyan] items across [bold]{len(db)}[/bold] resources!"
    )


def cli_entry():
    """Main CLI entrypoint routing default commands cleanly."""
    args = sys.argv[1:]
    # If no arguments, or first argument is not a known command and not a flag for help
    if not args:
        sys.argv.insert(1, "run")
    elif args[0] not in KNOWN_COMMANDS and not args[0].startswith("-"):
        sys.argv.insert(1, "run")
    elif args[0].startswith("-") and args[0] not in {"--help", "-h", "--version"}:
        sys.argv.insert(1, "run")

    app()


if __name__ == "__main__":
    cli_entry()

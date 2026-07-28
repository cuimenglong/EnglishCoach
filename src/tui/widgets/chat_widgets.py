from rich.markup import escape


def format_coach_message(content: str) -> str:
    return f"[bold green]Coach[/bold green]\n[green]{escape(content)}[/green]"


def format_user_message(content: str) -> str:
    return f"[bold white]You[/bold white]\n[white]{escape(content)}[/white]"


def format_system_message(content: str) -> str:
    return f"[italic yellow]  {escape(content)}[/italic yellow]"


def format_error_message(content: str) -> str:
    return f"[bold red]  ! {escape(content)}[/bold red]"

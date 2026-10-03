"""Message formatting for the chat log.

The coach's replies are rendered as Markdown. For a long time every prompt in
this project forbade Markdown ("output plain text only"), which suppressed the
model's best formatting and left the chat as one flat block of monospace. The
chat log accepts Rich renderables, so rendering Markdown costs nothing and
makes corrections and summaries far easier to scan.

User input is still escaped: it is displayed as literal text inside our own
markup, so a user typing "[bold]" must not be able to inject styling.
"""
from rich.console import Group
from rich.markup import escape
from rich.markdown import Markdown
from rich.text import Text


def format_coach_message(content: str) -> Markdown:
    """Coach replies render as Markdown so structure and emphasis come through."""
    return Markdown(content, justify="left")


def format_user_message(content: str) -> str:
    return f"[bold white]You[/bold white]\n[white]{escape(content)}[/white]"


def format_system_message(content: str) -> str:
    return f"[italic yellow]  {escape(content)}[/italic yellow]"


def format_error_message(content: str) -> str:
    return f"[bold red]  ! {escape(content)}[/bold red]"


def format_thinking(content: str) -> str:
    return f"[italic dim]  {escape(content)}[/italic dim]"


# --- small ASCII coach mark, shown in the sidebar -----------------------
# ASCII only on purpose: the app runs on Windows terminals that render many
# Unicode drawing characters as boxes, and anything wider than a couple of
# columns would fight the sidebar for space.
COACH_MARK = r"""
   .-------.
  /  o   o  \
 |     ^    |
  \  '---'  /
   '-------'
"""


def format_coach_mark() -> Text:
    return Text(COACH_MARK.strip("\n"), style="bold cyan", justify="center")

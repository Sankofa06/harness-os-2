"""Harness TUI — Textual client consuming the public API only (AGENTS.md).

Vertical-slice scope: connect, list/create a session, send a message, and render the
resulting conversation turns. Full navigation (SPEC/UI_UX.md IA) lands in TUI-003.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, ListItem, ListView, RichLog, Static

from harness.tui.client import HarnessClient


class HarnessTUI(App[None]):
    CSS = """
    #sidebar { width: 32; border-right: solid $accent; }
    #main { width: 1fr; }
    """
    BINDINGS: ClassVar = [("q", "quit", "Quit")]

    def __init__(self, api_base: str, token: str | None) -> None:
        super().__init__()
        self.client = HarnessClient(api_base, token)
        self.active_session_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Static("Sessions", classes="title")
                yield ListView(id="session_list")
            with Vertical(id="main"):
                yield RichLog(id="conversation", wrap=True, markup=True)
                yield Input(
                    placeholder="Message (use @handle to address a contact)…", id="composer"
                )
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_sessions()

    async def refresh_sessions(self) -> None:
        list_view = self.query_one("#session_list", ListView)
        await list_view.clear()
        sessions = await self.client.list_sessions()
        for session in sessions:
            title = session["title"] or session["id"]
            list_view.append(ListItem(Static(title), name=session["id"]))
        if sessions and self.active_session_id is None:
            self.active_session_id = sessions[0]["id"]

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.name:
            self.active_session_id = event.item.name
            self.query_one("#conversation", RichLog).clear()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if not self.active_session_id or not event.value.strip():
            return
        log = self.query_one("#conversation", RichLog)
        log.write(f"[bold]you[/bold]: {event.value}")
        response = await self.client.send_message(self.active_session_id, event.value)
        for run in response["runs"]:
            log.write(f"[bold cyan]{run['contact_handle']}[/bold cyan]: {run['content']}")
        self.query_one("#composer", Input).value = ""

    async def on_unmount(self) -> None:
        await self.client.close()


def run_tui(api_base: str, token: str | None = None) -> None:
    HarnessTUI(api_base, token).run()

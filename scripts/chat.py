#!/usr/bin/env python
import os
import sys
import uuid
import signal
from typing import Any

from app.agent import make_agent
from app.session import make_config, make_context, get_thread_state
from dotenv import load_dotenv

from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.table import Table

load_dotenv()

USER_NAME = os.getenv("USER_NAME", "Usuário")

console = Console()


def _format_cmds() -> str:
    return (
        "\nComandos: "
        "/id (mostra thread), "
        "/history (checkpoint atual), "
        "/exit (sair)\n"
    )


def _make_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_row(
        Layout(name="tools", ratio=1, minimum_size=40),
        Layout(name="chat", ratio=2, minimum_size=60),
    )
    return layout


def _render_tools_panel(tools_log: list[str]) -> Panel:
    table = Table.grid(expand=True)
    table.add_column(justify="left")
    if not tools_log:
        table.add_row("[dim]Sem chamadas de tools ainda[/dim]")
    else:
        for line in tools_log[-200:]:
            table.add_row(line)
    return Panel(
        table,
        title="⚙️ Tools",
        border_style="cyan",
        title_align="left",
    )


def _render_chat_panel(chat_lines: list[str]) -> Panel:
    md = Markdown("\n\n".join(chat_lines[-200:]) or "[dim]Comece a conversar[/dim]")
    return Panel(md, title="💬 Chat", border_style="magenta", title_align="left")


def main() -> None:
    thread_id = f"{USER_NAME}:{uuid.uuid4()}"
    console.print(f"[bold]🧵 nova thread:[/bold] [green]{thread_id}[/green]")
    console.print(_format_cmds())

    agent, _store = make_agent(user_id=USER_NAME, thread_id=thread_id)

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    tools_log: list[str] = []
    chat_lines: list[str] = []
    layout = _make_layout()
    layout["tools"].update(_render_tools_panel(tools_log))
    layout["chat"].update(_render_chat_panel(chat_lines))

    with Live(layout, refresh_per_second=12, console=console, screen=False):
        while True:
            try:
                user_text = console.input("[bold cyan]\nyou>[/bold cyan] ").strip()
            except EOFError:
                console.print()
                break

            if not user_text:
                continue

            # Utility commands
            if user_text.lower() in ("/exit", "exit", "quit", ":q"):
                console.print("👋 saindo…")
                break

            if user_text.lower() in ("/id", "id"):
                console.print(f"thread_id: [yellow]{thread_id}[/yellow]")
                continue

            if user_text.lower() in ("/history", "history"):
                snap = get_thread_state(agent, thread_id, user_id=USER_NAME)
                ckpt = snap.config["configurable"].get("checkpoint_id")
                step = snap.metadata.get("step")
                console.print(f"checkpoint_id atual: [yellow]{ckpt}[/yellow] | step: [yellow]{step}[/yellow]")
                continue

            cfg = make_config(thread_id, user_id=USER_NAME)
            ctx = make_context(
                user_id=USER_NAME,
                locale="pt-BR",
                currency="BRL",
                timezone="America/Sao_Paulo",
                recursion_limit=6,
            )

            # Update chat with user message
            chat_lines.append(f"**you**: {user_text}")
            layout["chat"].update(_render_chat_panel(chat_lines))

            try:
                # Stream both messages and updates to capture tool activity
                for mode, chunk in agent.stream(
                    {"messages": [{"role": "user", "content": user_text}]},
                    context=ctx,
                    config=cfg,
                    stream_mode=["messages", "updates"],
                ):
                    if mode == "messages":
                        msg_chunk, _meta = chunk
                        content = getattr(msg_chunk, "content", "")
                        if isinstance(content, str) and content:
                            if chat_lines and chat_lines[-1].startswith("**assistant**:"):
                                chat_lines[-1] += content
                            else:
                                chat_lines.append(f"**assistant**: {content}")
                            layout["chat"].update(_render_chat_panel(chat_lines))
                        elif isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict) and part.get("type") == "text" and "text" in part:
                                    text = part["text"]
                                    if chat_lines and chat_lines[-1].startswith("**assistant**:"):
                                        chat_lines[-1] += text
                                    else:
                                        chat_lines.append(f"**assistant**: {text}")
                                    layout["chat"].update(_render_chat_panel(chat_lines))
                    elif mode == "updates":
                        # updates stream contains tool execution traces
                        try:
                            line = str(chunk)
                            if "tool" in line.lower():
                                line = f"[cyan]{line}[/cyan]"
                            elif "error" in line.lower():
                                line = f"[red]{line}[/red]"
                            tools_log.append(line)
                            layout["tools"].update(_render_tools_panel(tools_log))
                        except Exception:
                            pass
                # spacing between turns
                chat_lines.append("")
                layout["chat"].update(_render_chat_panel(chat_lines))
            except Exception as e:
                console.print(f"[red]\n[erro no streaming] {e}[/red]")


if __name__ == "__main__":
    main()
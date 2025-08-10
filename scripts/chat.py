#!/usr/bin/env python
import os
import sys
import uuid
import signal
from typing import Any, Iterable, Tuple

from app.agent import make_agent
from app.session import make_config, make_context, get_thread_state
from dotenv import load_dotenv

load_dotenv()

USER_NAME = os.getenv("USER_NAME", "Usuário")

# -------- helpers --------
def _print_token_chunk(message_chunk: Any) -> None:
    """
    Print token chunks when using stream_mode="messages".
    Handles content as str or list (multipart).
    """
    content = getattr(message_chunk, "content", "")
    if isinstance(content, str):
        # direct text token
        print(content, end="", flush=True)
    elif isinstance(content, list):
        # multimodal/text parts
        for part in content:
            # typical dict part: {"type": "text", "text": "..."}
            if isinstance(part, dict) and part.get("type") == "text" and "text" in part:
                print(part["text"], end="", flush=True)

def _format_cmds() -> str:
    return (
        "\nComandos: "
        "/id (mostra thread), "
        "/history (checkpoint atual), "
        "/exit (sair)\n"
    )

# -------- main loop --------
def main() -> None:
    # New chat each run: thread_id = "user1:<uuid4>"
    thread_id = f"{USER_NAME}:{uuid.uuid4()}"
    print(f"🧵 nova thread: {thread_id}")
    print(_format_cmds())

    # Create agent (with sqlite checkpointer + persistent store + long-term memories)
    agent, store = make_agent(user_id=USER_NAME, thread_id=thread_id)

    # Friendly Ctrl+C
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    while True:
        try:
            user_text = input("\nyou> ").strip()
        except EOFError:
            print()
            break

        if not user_text:
            continue

        # Utility commands
        if user_text.lower() in ("/exit", "exit", "quit", ":q"):
            print("👋 saindo…")
            break

        if user_text.lower() in ("/id", "id"):
            print(f"thread_id: {thread_id}")
            continue

        if user_text.lower() in ("/history", "history"):
            snap = get_thread_state(agent, thread_id, user_id=USER_NAME)
            ckpt = snap.config["configurable"].get("checkpoint_id")
            step = snap.metadata.get("step")
            print(f"checkpoint_id atual: {ckpt} | step: {step}")
            continue

        # Config and context for this run
        cfg = make_config(thread_id, user_id=USER_NAME)
        ctx = make_context(
            user_id=USER_NAME,
            locale="pt-BR",
            currency="BRL",
            timezone="America/Sao_Paulo",
            recursion_limit=6,
        )

        # Token streaming from model
        print("assistant> ", end="", flush=True)
        try:
            # stream_mode="messages" for token-level streaming; you may include "updates" for debug
            for mode, chunk in agent.stream(
                {"messages": [{"role": "user", "content": user_text}]},
                context=ctx,
                config=cfg,
                stream_mode=["messages"],
            ):
                if mode == "messages":
                    msg_chunk, _meta = chunk  # (message_chunk, metadata)
                    _print_token_chunk(msg_chunk)
            print("")  # quebra de linha ao final da resposta
        except Exception as e:
            print(f"\n[erro no streaming] {e}")
            # common hint: check your API key in .env

if __name__ == "__main__":
    main()
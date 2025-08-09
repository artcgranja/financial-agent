#!/usr/bin/env python
import sys
import uuid
import signal
from typing import Any, Iterable, Tuple

from app.agent import make_agent
from app.session import make_config, make_context, get_thread_state

# -------- helpers --------
def _print_token_chunk(message_chunk: Any) -> None:
    """
    Imprime os tokens do chunk de mensagens do stream_mode="messages".
    Lida com content=str ou content=list (multipart).
    """
    content = getattr(message_chunk, "content", "")
    if isinstance(content, str):
        # token textual direto
        print(content, end="", flush=True)
    elif isinstance(content, list):
        # multimodal/text parts
        for part in content:
            # part é dict do tipo {"type": "text", "text": "..."} em integrações comuns
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
    # Novo chat sempre: thread_id = "user1:<uuid4>"
    user_id = "user1"
    thread_id = f"{user_id}:{uuid.uuid4()}"
    print(f"🧵 nova thread: {thread_id}")
    print(_format_cmds())

    # Cria agente (sem tools; com checkpointer sqlite + store persistente se você já integrou)
    agent = make_agent()

    # Ctrl+C amigável
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    while True:
        try:
            user_text = input("\nyou> ").strip()
        except EOFError:
            print()
            break

        if not user_text:
            continue

        # Comandos utilitários
        if user_text.lower() in ("/exit", "exit", "quit", ":q"):
            print("👋 saindo…")
            break

        if user_text.lower() in ("/id", "id"):
            print(f"thread_id: {thread_id}")
            continue

        if user_text.lower() in ("/history", "history"):
            snap = get_thread_state(agent, thread_id, user_id=user_id)
            ckpt = snap.config["configurable"].get("checkpoint_id")
            step = snap.metadata.get("step")
            print(f"checkpoint_id atual: {ckpt} | step: {step}")
            continue

        # Config e context para este run
        cfg = make_config(thread_id, user_id=user_id)
        ctx = make_context(
            user_id=user_id,
            locale="pt-BR",
            currency="BRL",
            timezone="America/Sao_Paulo",
            recursion_limit=6,
        )

        # Stream dos tokens do modelo
        print("assistant> ", end="", flush=True)
        try:
            # stream_mode="messages" para tokens; você pode incluir "updates" p/ debug
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
            # dica comum: checar OPENAI_API_KEY no .env

if __name__ == "__main__":
    main()
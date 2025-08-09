from typing import Any, Dict, Iterable, Tuple

# Tip: manter esse módulo sem dependências fortes além do agente
def make_config(thread_id: str, user_id: str | None = None) -> Dict[str, Any]:
    # Threads e replay usam config['configurable']
    cfg: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if user_id:
        cfg["configurable"]["user_id"] = user_id
    return cfg

def make_context(
    user_id: str | None = None,
    locale: str = "pt-BR",
    currency: str = "BRL",
    timezone: str = "America/Sao_Paulo",
    recursion_limit: int | None = 6,
) -> Dict[str, Any]:
    # Runtime context imutável por execução (LangGraph ≥ 0.6)
    ctx: Dict[str, Any] = {
        "user_id": user_id,
        "locale": locale,
        "currency": currency,
        "timezone": timezone,
    }
    # Você pode passar recursion_limit via with_config no agente também; manter aqui por praticidade
    if recursion_limit is not None:
        ctx["_recursion_limit"] = recursion_limit
    return ctx

def send_message(agent, thread_id: str, text: str, *, user_id: str | None = None) -> Dict[str, Any]:
    cfg = make_config(thread_id, user_id)
    ctx = make_context(user_id=user_id)
    return agent.invoke({"messages": [{"role": "user", "content": text}]}, context=ctx, config=cfg)

def stream_message(
    agent, thread_id: str, text: str, *, user_id: str | None = None, modes: Iterable[str] = ("updates",)
) -> Iterable[Tuple[str, Any]]:
    cfg = make_config(thread_id, user_id)
    ctx = make_context(user_id=user_id)
    # Quando passar múltiplos modos, o yield é (mode, chunk)
    for item in agent.stream({"messages": [{"role": "user", "content": text}]}, context=ctx, config=cfg, stream_mode=list(modes)):
        yield item

def get_thread_state(agent, thread_id: str, *, user_id: str | None = None):
    cfg = make_config(thread_id, user_id)
    return agent.get_state(cfg)

def get_thread_history(agent, thread_id: str, *, user_id: str | None = None):
    cfg = make_config(thread_id, user_id)
    return list(agent.get_state_history(cfg))

def get_thread_messages(agent, thread_id: str, *, user_id: str | None = None):
    """Retorna a lista de mensagens (user/assistant/tool) do último checkpoint da thread."""
    cfg = {"configurable": {"thread_id": thread_id}}
    if user_id:
        cfg["configurable"]["user_id"] = user_id

    snap = agent.get_state(cfg)  # StateSnapshot mais recente
    msgs = snap.values.get("messages", [])
    # Normaliza para algo simples pro front
    out = []
    for m in msgs:
        role = getattr(m, "role", None) or m.__class__.__name__.lower()
        content = getattr(m, "content", "")
        tool_calls = getattr(m, "tool_calls", None)
        name = getattr(m, "name", None)
        out.append(
            {
                "role": role,             # "user", "assistant", "tool", ...
                "content": content,       # string ou lista de partes (pode precisar tratar multimodal)
                "name": name,             # nome da tool (quando for ToolMessage)
                "tool_calls": tool_calls, # se o assistant pediu tool(s)
            }
        )
    return out
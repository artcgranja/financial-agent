# app/agent.py
"""
Personal financial assistant using LangGraph with persistent memory + long-term memories (langmem).
"""
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langmem import create_manage_memory_tool, create_search_memory_tool
from langgraph.store.memory import InMemoryStore


from app.store import PersistentSQLiteStore
from app.tools import create_financial_tools

load_dotenv()

# Settings
DEFAULT_MODEL = os.getenv("MODEL_NAME", "anthropic:claude-sonnet-4-20250514")
CHECKPOINT_DB = os.getenv("CHECKPOINT_DB", "checkpoint.db")
STORE_DB = os.getenv("STORE_DB", "financial_store.db")
USER_NAME = os.getenv("USER_NAME", "Usuário")

# Timezone and current date
NOW_SP = datetime.now(ZoneInfo(os.getenv("TZ", "America/Sao_Paulo")))
TODAY_DATE = NOW_SP.strftime("%d/%m/%Y %H:%M:%S %Z")

# System prompt (English)
SYSTEM_PROMPT = f"""You are a personal assistant specialized in personal finance tracking.

CONTEXT:
- User: {USER_NAME}
- Current date/time: {TODAY_DATE}
- Currency: Brazilian Real (R$)

PRIMARY RESPONSIBILITIES:
1) Record incomes and expenses mentioned in the conversation
2) Provide summaries and analyses upon request
3) Help categorize transactions automatically
4) Answer questions about the financial status

INTERACTION GUIDELINES:
- Be concise and friendly
- Always confirm recorded values
- Use Brazilian currency format (R$ 1.234,56)
- If no date is mentioned, assume "today"
- Infer category when possible from the description
- Ask for more details only if essential

DEFAULT CATEGORIES:
- Expenses: Alimentação, Transporte, Moradia, Saúde, Educação, Lazer, Compras, Serviços, Assinaturas
- Income: Salário, Freelance, Investimentos, Vendas, Reembolso, Presente

EXAMPLES:
- "Gastei 45 no almoço" → Record an expense of R$ 45 under Alimentação
- "Recebi 5000 de salário" → Record an income of R$ 5000 under Salário
- "Paguei 120 de uber este mês" → Record an expense of R$ 120 under Transporte

IMPORTANT:
- Always use the available tools to record and query data
- Do not hallucinate values or transactions — always consult the database
- Be transparent about what was recorded
- Use the provided tools to create, search, and manage long-term memories (facts, preferences, recurring info) when helpful.
"""


def build_checkpointer(db_path: str = CHECKPOINT_DB) -> SqliteSaver:
    """Builds the SQLite checkpointer for graph state persistence."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def make_agent(
    model_name: str = DEFAULT_MODEL,
    user_id: str | None = None,
    thread_id: str | None = None,
):
    """
    Create the financial agent with all tools configured.
    
    Args:
        model_name: LLM model name
        user_id: Current user id (defaults to USER_NAME if not provided)
        thread_id: Conversation thread id
    
    Returns:
        Compiled agent and the persistent store
    """

    # Initialize model
    model = init_chat_model(model_name, temperature=0)

    # Persistence for conversation state and financial DB
    checkpointer = build_checkpointer()
    financial_store = PersistentSQLiteStore(STORE_DB)

    # Financial tools
    tools = create_financial_tools(
        store=financial_store,
        user_id=user_id,
        thread_id=thread_id,
    )

    # Long-term memory store (vector-backed)
    index_config = {
        "dims": int(os.getenv("LMEM_EMBED_DIMS", "1536")),
        "embed": os.getenv("LMEM_EMBED_MODEL", "openai:text-embedding-3-small"),
    }
    memory_store = InMemoryStore(index=index_config)
    namespace = ("memories", user_id)

    # Memory management/search tools
    tools.extend(
        [
            create_manage_memory_tool(namespace=namespace),
            create_search_memory_tool(namespace=namespace),
        ]
    )

    # Bind tools to model
    model_with_tools = model.bind_tools(tools, parallel_tool_calls=False)

    # Prompt that injects retrieved memories
    def _prompt_with_memories(state):
        # Extract latest user text (handles dicts or LC message objects)
        try:
            last_msg = state["messages"][-1]
            user_text = getattr(last_msg, "content", None) or (
                last_msg.get("content") if isinstance(last_msg, dict) else None
            )
        except Exception:
            user_text = None

        memories = []
        if user_text:
            try:
                memories = memory_store.search(namespace, query=user_text)
            except Exception:
                memories = []

        system_msg = (
            f"{SYSTEM_PROMPT}\n\n"
            f"## Memories\n"
            f"<memories>\n{memories}\n</memories>\n"
        )
        return [{"role": "system", "content": system_msg}, *state["messages"]]

    # Create ReAct agent with memory store + checkpointing
    agent = create_react_agent(
        model=model_with_tools,
        tools=tools,
        prompt=_prompt_with_memories,
        checkpointer=checkpointer,
        store=memory_store,
    )

    return agent, financial_store
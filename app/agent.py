# app/agent.py
"""
Personal financial assistant using LangGraph with persistent memory.
"""
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver

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
- Be transparent about what was recorded"""


def build_checkpointer(db_path: str = CHECKPOINT_DB) -> SqliteSaver:
    """Builds the SQLite checkpointer for graph state persistence."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def make_agent(
    model_name: str = DEFAULT_MODEL,
    user_id: str = None,
    thread_id: str = None
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
    # Configure user_id
    if user_id is None:
        user_id = USER_NAME
    
    # Initialize model
    model = init_chat_model(model_name, temperature=0)
    
    # Persistence
    checkpointer = build_checkpointer()
    store = PersistentSQLiteStore(STORE_DB)
    
    # Create tools
    tools = create_financial_tools(
        store=store,
        user_id=user_id,
        thread_id=thread_id
    )
    
    # Bind tools to the model
    model_with_tools = model.bind_tools(tools, parallel_tool_calls=False)
    
    # Create ReAct agent
    agent = create_react_agent(
        model=model_with_tools,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    
    return agent, store
import os
import sqlite3
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from app.store import PersistentSQLiteStore
from datetime import datetime

load_dotenv()

DEFAULT_MODEL = os.getenv("MODEL_NAME", "anthropic:claude-sonnet-4-20250514")
CHECKPOINT_DB = os.getenv("CHECKPOINT_DB", "checkpoint.db")
STORE_DB = os.getenv("STORE_DB", "store.db")
USER_NAME = os.getenv("USER_NAME", "Monkey D. Luffy")
TODAY_DATE = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

SYSTEM_PROMPT = (
    "<role>You are a expert financial advisor and financial accountant.</role>"
    f"<context>You are talking with {USER_NAME}, today date is {TODAY_DATE}.</context>"
    "<goal>Your goal is to help the user with their financial questions and provide financial advice and management through the use of tools.</goal>"
    "<instructions>Be direct and polite. Ask for clarification when needed. For now, you are just a chatbot (without tools).</instructions>"
)

def build_checkpointer(db_path: str = CHECKPOINT_DB) -> SqliteSaver:
    # check_same_thread=False para uso seguro em apps que possam reusar a conexão
    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver

def make_agent(model_name: str = DEFAULT_MODEL):
    model = init_chat_model(model_name, temperature=0, streaming=True)

    checkpointer = build_checkpointer()
    store = PersistentSQLiteStore(STORE_DB)

    agent = create_react_agent(
        model=model,
        tools=[],
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        store=store,  # <- long-term memory persistente
    )
    return agent
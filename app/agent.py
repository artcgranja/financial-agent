# app/agent.py
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver

from app.store import PersistentSQLiteStore
from app.tools.memory import (
    set_preference,
    save_budget,
    teach_category_rule,
    get_preference,
    get_budget,
    get_category_rule,
)

load_dotenv()

DEFAULT_MODEL = os.getenv("MODEL_NAME", "anthropic:claude-sonnet-4-20250514")
CHECKPOINT_DB = os.getenv("CHECKPOINT_DB", "checkpoint.db")
STORE_DB = os.getenv("STORE_DB", "store.db")
USER_NAME = os.getenv("USER_NAME", "Monkey D. Luffy")

# Data/hora local em São Paulo (pode sobrescrever com TZ no .env)
NOW_SP = datetime.now(ZoneInfo(os.getenv("TZ", "America/Sao_Paulo")))
TODAY_DATE = NOW_SP.strftime("%d/%m/%Y %H:%M:%S %Z")

SYSTEM_PROMPT = (
    "<role>Você é um consultor financeiro e contador experiente.</role>\n"
    f"<context>Você está conversando com {USER_NAME}. Data/hora local: {TODAY_DATE}.</context>\n"
    "<capabilities>Você pode conversar e chamar ferramentas quando apropriado:\n"
    "- set_preference(key, value): salva preferências do usuário (ex.: currency, timezone, monthly_income, confirm_threshold).\n"
    "- save_budget(category, amount, period?, currency?): define orçamento por categoria e período (YYYY-MM).\n"
    "- teach_category_rule(merchant, category): cria regra de categorização por estabelecimento.\n"
    "- get_preference(key?): lê preferências (uma chave específica ou todo o perfil).\n"
    "- get_budget(category?, period?, limit?): consulta orçamento por categoria/periodo ou lista do período.\n"
    "- get_category_rule(merchant): consulta regra de categorização para um estabelecimento.</capabilities>\n"
    "<tool_usage_rules>\n"
    "1) Antes de pedir ao usuário algo que pode já existir (ex.: renda, moeda, orçamento), TENTE consultar com a tool de leitura apropriada.\n"
    "2) Se a informação não existir, aí sim pergunte de forma objetiva e, quando receber, chame a tool de escrita correspondente.\n"
    "3) Use no máximo uma ferramenta por vez; não invente dados.\n"
    "4) Após executar uma ferramenta, responda confirmando a informação/alteração de forma breve.\n"
    "5) Responda sempre em pt-BR, de forma direta e educada.</tool_usage_rules>\n"
    "<style>Seja claro, conciso e proativo, sem assumir fatos não verificados.</style>"
)

def build_checkpointer(db_path: str = CHECKPOINT_DB) -> SqliteSaver:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver

def make_agent(model_name: str = DEFAULT_MODEL):
    model = init_chat_model(model_name, temperature=0)

    checkpointer = build_checkpointer()
    store = PersistentSQLiteStore(STORE_DB)

    tools = [
        # leitura primeiro encoraja checagem antes de perguntar
        get_preference, get_budget, get_category_rule,
        # escrita
        set_preference, save_budget, teach_category_rule,
    ]

    model_with_tools = model.bind_tools(tools, parallel_tool_calls=False)

    agent = create_react_agent(
        model=model_with_tools,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        store=store,
    )
    return agent
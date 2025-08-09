# app/agent.py
"""
Agente financeiro pessoal usando LangGraph com memória persistente
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

# Configurações
DEFAULT_MODEL = os.getenv("MODEL_NAME", "anthropic:claude-sonnet-4-20250514")
CHECKPOINT_DB = os.getenv("CHECKPOINT_DB", "checkpoint.db")
STORE_DB = os.getenv("STORE_DB", "financial_store.db")
USER_NAME = os.getenv("USER_NAME", "Usuário")

# Timezone e data atual
NOW_SP = datetime.now(ZoneInfo(os.getenv("TZ", "America/Sao_Paulo")))
TODAY_DATE = NOW_SP.strftime("%d/%m/%Y %H:%M:%S %Z")

# System prompt otimizado para tracking financeiro
SYSTEM_PROMPT = f"""Você é um assistente pessoal especializado em controle financeiro.

CONTEXTO:
- Usuário: {USER_NAME}
- Data/hora atual: {TODAY_DATE}
- Moeda: Real Brasileiro (R$)

RESPONSABILIDADES PRINCIPAIS:
1. Registrar receitas e despesas mencionadas na conversa
2. Fornecer resumos e análises quando solicitado
3. Ajudar a categorizar transações automaticamente
4. Responder perguntas sobre o estado financeiro

DIRETRIZES DE INTERAÇÃO:
- Seja conciso e amigável
- Sempre confirme valores registrados
- Use formato brasileiro para moeda (R$ 1.234,56)
- Se a data não for mencionada, assuma "hoje"
- Infira categoria quando possível pela descrição
- Pergunte detalhes apenas se essencial

CATEGORIAS PADRÃO:
- Despesas: Alimentação, Transporte, Moradia, Saúde, Educação, Lazer, Compras, Serviços, Assinaturas
- Receitas: Salário, Freelance, Investimentos, Vendas, Reembolso, Presente

EXEMPLOS DE INTERAÇÃO:
- "Gastei 45 no almoço" → Registra despesa de R$ 45 em Alimentação
- "Recebi 5000 de salário" → Registra receita de R$ 5000 em Salário
- "Paguei 120 de uber este mês" → Registra despesa de R$ 120 em Transporte

IMPORTANTE:
- Sempre use as ferramentas disponíveis para registrar e consultar dados
- Não invente valores ou transações - consulte sempre o banco de dados
- Seja transparente sobre o que foi registrado"""


def build_checkpointer(db_path: str = CHECKPOINT_DB) -> SqliteSaver:
    """Constrói o checkpointer SQLite para persistência de estado do grafo"""
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
    Cria o agente financeiro com todas as ferramentas configuradas.
    
    Args:
        model_name: Nome do modelo LLM a usar
        user_id: ID do usuário (usa USER_NAME do .env se não fornecido)
        thread_id: ID da thread de conversa
    
    Returns:
        Agente compilado pronto para uso
    """
    # Configurar user_id
    if user_id is None:
        user_id = USER_NAME
    
    # Inicializar modelo
    model = init_chat_model(model_name, temperature=0)
    
    # Configurar persistência
    checkpointer = build_checkpointer()
    store = PersistentSQLiteStore(STORE_DB)
    
    # Criar ferramentas financeiras
    tools = create_financial_tools(
        store=store,
        user_id=user_id,
        thread_id=thread_id
    )
    
    # Bind tools ao modelo
    model_with_tools = model.bind_tools(tools, parallel_tool_calls=False)
    
    # Criar agente ReAct
    agent = create_react_agent(
        model=model_with_tools,
        tools=tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    
    return agent, store
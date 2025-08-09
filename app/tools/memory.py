from __future__ import annotations
import unicodedata
import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store


# ---------- utils ----------

def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return "-".join(s.strip().lower().split())

def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _get_user_id(config: RunnableConfig) -> str:
    return (config or {}).get("configurable", {}).get("user_id", "user1")


# ---------- Tool 1: set_preference ----------

class SetPreferenceInput(BaseModel):
    """Define ou atualiza uma preferência do usuário."""
    key: str = Field(description="Nome da preferência (ex.: 'currency', 'timezone', 'confirm_threshold')")
    value: Any = Field(description="Valor da preferência (qualquer JSON)")

    @field_validator("key")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("key vazio")
        return v.strip()

@tool("set_preference", args_schema=SetPreferenceInput)
def set_preference(key: str, value: Any, config: RunnableConfig) -> str:
    """
    Salva uma preferência do usuário no store em (user_id, 'prefs') com key 'profile'.
    Ex.: currency=BRL, timezone=America/Sao_Paulo, confirm_threshold=500
    """
    store = get_store()
    user_id = _get_user_id(config)
    ns = (user_id, "prefs")

    # Carrega perfil existente
    current = store.get(ns, "profile")
    profile = (current["value"] if current else {}) or {}

    # Upsert
    profile[key] = value
    store.put(ns, "profile", profile)

    return f"Preferência salva: {key}={value}"


# ---------- Tool 2: save_budget ----------

class SaveBudgetInput(BaseModel):
    """Cria/atualiza orçamento para uma categoria em um período (YYYY-MM)."""
    category: str = Field(description="Nome da categoria (ex.: 'Restaurantes')")
    amount: float = Field(description="Valor do orçamento numérico (mesma moeda das prefs)")
    period: Optional[str] = Field(default=None, description="Período no formato YYYY-MM; default = mês atual")
    currency: Optional[str] = Field(default=None, description="Moeda (override opcional das prefs)")

    @field_validator("category")
    @classmethod
    def _category_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("category vazia")
        return v.strip()

    @field_validator("period")
    @classmethod
    def _period_fmt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        try:
            dt.datetime.strptime(v, "%Y-%m")  # valida formato
            return v
        except Exception:
            raise ValueError("period deve estar no formato YYYY-MM")

@tool("save_budget", args_schema=SaveBudgetInput)
def save_budget(category: str, amount: float, period: Optional[str], currency: Optional[str], config: RunnableConfig) -> str:
    """
    Salva orçamento por categoria/periodo no store em (user_id, 'budgets').
    A chave é '{period}:{slug(category)}'. Se currency não for informada, usa prefs.currency (ou 'BRL').
    """
    store = get_store()
    user_id = _get_user_id(config)

    # Definir período
    if not period:
        today = dt.date.today()
        period = f"{today.year:04d}-{today.month:02d}"

    # Moeda padrão das prefs
    if not currency:
        prefs = store.get((user_id, "prefs"), "profile")
        currency = (prefs["value"].get("currency") if prefs else None) or "BRL"

    key = f"{period}:{_slug(category)}"
    value = {
        "category": category,
        "amount": float(amount),
        "period": period,
        "currency": currency,
        "updated_at": _now_iso(),
    }
    store.put((user_id, "budgets"), key, value)
    return f"Orçamento salvo: {category} = {amount} {currency} em {period}"


# ---------- Tool 3: teach_category_rule ----------

class TeachRuleInput(BaseModel):
    """Ensina uma regra de categorização: merchant → category."""
    merchant: str = Field(description='Nome do estabelecimento (ex.: "Padaria São João")')
    category: str = Field(description='Categoria destino (ex.: "Restaurantes")')

    @field_validator("merchant", "category")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("campo vazio")
        return v.strip()

@tool("teach_category_rule", args_schema=TeachRuleInput)
def teach_category_rule(merchant: str, category: str, config: RunnableConfig) -> str:
    """
    Cria/atualiza uma regra de categorização no store em (user_id, 'rules').
    Chave: slug do merchant. Valor: {merchant, category, updated_at}.
    """
    store = get_store()
    user_id = _get_user_id(config)

    key = _slug(merchant)
    value = {
        "merchant": merchant,
        "category": category,
        "updated_at": _now_iso(),
    }
    store.put((user_id, "rules"), key, value)
    return f"Regra salva: '{merchant}' → '{category}'"

class GetPreferenceInput(BaseModel):
    """Lê preferências do usuário. Se 'key' for fornecida, retorna só aquela chave; caso contrário, retorna o perfil inteiro."""
    key: Optional[str] = Field(default=None, description="Nome da preferência (ex.: 'currency', 'timezone', 'monthly_income'). Opcional.")

@tool("get_preference", args_schema=GetPreferenceInput)
def get_preference(key: Optional[str], config: RunnableConfig) -> str:
    store = get_store()
    user_id = (config or {}).get("configurable", {}).get("user_id", "user1")
    item = store.get((user_id, "prefs"), "profile")
    if not item or not item.get("value"):
        return "Nenhuma preferência encontrada."
    profile = item["value"]
    if key:
        return f"{key}={profile.get(key)!r}" if key in profile else f"Preferência '{key}' não encontrada."
    return str(profile)

# ---------- Read Tool B: get_budget (por categoria/periodo) ----------

class GetBudgetInput(BaseModel):
    """Lê orçamento(s). Se 'category' não for informada, lista do período."""
    category: Optional[str] = Field(default=None, description="Nome da categoria (ex.: 'Restaurantes'). Opcional.")
    period: Optional[str] = Field(default=None, description="Período YYYY-MM. Se ausente, usa mês atual.")
    limit: int = Field(default=20, description="Máximo de itens ao listar sem categoria.")

@tool("get_budget", args_schema=GetBudgetInput)
def get_budget(category: Optional[str], period: Optional[str], limit: int, config: RunnableConfig) -> str:
    import datetime as dt
    store = get_store()
    user_id = (config or {}).get("configurable", {}).get("user_id", "user1")

    if not period:
        today = dt.date.today()
        period = f"{today.year:04d}-{today.month:02d}"

    ns = (user_id, "budgets")
    if category:
        # chave direta
        key = f"{period}:{_slug(category)}"
        item = store.get(ns, key)
        return str(item["value"]) if item else f"Nenhum orçamento para '{category}' em {period}."
    # lista por período
    rows = store.search(ns, filter={"period": period}, limit=limit)
    if not rows:
        return f"Nenhum orçamento encontrado para {period}."
    return str([r["value"] for r in rows])

# ---------- Read Tool C: get_category_rule (por merchant) ----------

class GetRuleInput(BaseModel):
    """Obtém regra de categorização por estabelecimento."""
    merchant: str = Field(description='Nome do estabelecimento (ex.: "Padaria São João")')

@tool("get_category_rule", args_schema=GetRuleInput)
def get_category_rule(merchant: str, config: RunnableConfig) -> str:
    store = get_store()
    user_id = (config or {}).get("configurable", {}).get("user_id", "user1")
    key = _slug(merchant)
    item = store.get((user_id, "rules"), key)
    return str(item["value"]) if item else f"Nenhuma regra encontrada para '{merchant}'."
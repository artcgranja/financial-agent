"""
Ferramentas financeiras com schemas Pydantic (sem classe), prontas para LangChain.
"""
from typing import Literal, Optional, List, Dict, Any, Callable
from datetime import datetime, date
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool
from app.store import PersistentSQLiteStore


# ---------------- Pydantic Schemas ----------------
class AddTransactionInput(BaseModel):
    amount: float = Field(..., description="Valor positivo da transação")
    type: Literal["income", "expense"] = Field(..., description="Tipo da transação")
    category: Optional[str] = Field(None, description="Categoria (opcional, será inferida)")
    description: Optional[str] = Field(None, description="Descrição (opcional)")
    date_str: Optional[str] = Field(
        None,
        description="Data em 'YYYY-MM-DD' ou 'DD/MM/YYYY' (opcional, usa hoje)",
    )


class GetBalanceInput(BaseModel):
    period: Literal["today", "week", "month", "year", "all"] = Field(
        "month", description="Período do resumo"
    )


class ListTransactionsInput(BaseModel):
    limit: int = Field(10, description="Número máximo de transações")
    type: Optional[Literal["income", "expense"]] = Field(None, description="Filtro por tipo")
    period: Optional[Literal["today", "week", "month", "year"]] = Field(
        None, description="Filtro por período"
    )
    category: Optional[str] = Field(None, description="Filtro por categoria")


class GetCategorySummaryInput(BaseModel):
    period: Literal["today", "week", "month", "year"] = Field(
        "month", description="Período do resumo"
    )


class SearchTransactionsInput(BaseModel):
    search_term: str = Field(..., description="Termo a buscar")
    limit: int = Field(5, description="Número máximo de resultados")


# ---------------- Helpers ----------------
def _format_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------- Tool Factories ----------------
def _make_add_transaction(store: PersistentSQLiteStore, user_id: str, thread_id: Optional[str]) -> StructuredTool:
    def run(amount: float, type: Literal["income", "expense"], category: Optional[str] = None, description: Optional[str] = None, date_str: Optional[str] = None) -> str:
        try:
            # Inferir categoria se não fornecida
            if not category and description:
                inferred_category, inferred_type = store.infer_category(description)
                category = category or inferred_category
                if description and not type:
                    type = inferred_type  # type: ignore
            elif not category:
                category = "Outros"

            # Converter string de data se fornecida
            transaction_date = None
            if date_str:
                try:
                    transaction_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        transaction_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                    except ValueError:
                        pass

            transaction_id = store.add_transaction(
                user_id=user_id,
                amount=abs(amount),
                type=type,
                category=category or "Outros",
                description=description,
                transaction_date=transaction_date,
                thread_id=thread_id,
            )

            type_text = "Receita" if type == "income" else "Despesa"
            date_text = transaction_date.strftime("%d/%m/%Y") if transaction_date else "hoje"
            return (
                f"✅ {type_text} registrada com sucesso!\n"
                f"💰 Valor: {_format_brl(amount)}\n"
                f"📁 Categoria: {category}\n"
                f"📅 Data: {date_text}\n"
                f"🆔 ID: #{transaction_id}"
                + (f"\n📝 Descrição: {description}" if description else "")
            )
        except Exception as e:
            return f"❌ Erro ao registrar transação: {str(e)}"

    return StructuredTool.from_function(
        name="add_transaction",
        description=(
            "Adiciona uma nova transação financeira. Se categoria não for informada,"
            " será inferida pela descrição. Aceita datas em YYYY-MM-DD ou DD/MM/YYYY."
        ),
        func=run,
        args_schema=AddTransactionInput,
    )


def _make_get_balance(store: PersistentSQLiteStore, user_id: str) -> StructuredTool:
    def run(period: Literal["today", "week", "month", "year", "all"] = "month") -> str:
        try:
            data = store.get_balance(user_id, period)
            income = _format_brl(data["income"])
            expenses = _format_brl(data["expenses"])
            balance = data["balance"]
            balance_formatted = _format_brl(abs(balance))
            balance_emoji = "🟢" if balance >= 0 else "🔴"
            period_text = {
                "today": "Hoje",
                "week": "Última semana",
                "month": "Este mês",
                "year": "Este ano",
                "all": "Todo o período",
            }.get(period, period)
            resp = (
                f"📊 **Resumo Financeiro - {period_text}**\n\n"
                f"📈 Receitas: {income}\n"
                f"📉 Despesas: {expenses}\n"
                f"{'─' * 30}\n"
                f"{balance_emoji} Saldo: {balance_formatted}"
            )
            if balance < 0:
                resp += " (negativo)"
            return resp
        except Exception as e:
            return f"❌ Erro ao obter balanço: {str(e)}"

    return StructuredTool.from_function(
        name="get_balance",
        description="Obtém o resumo (receitas, despesas, saldo) para um período.",
        func=run,
        args_schema=GetBalanceInput,
    )


def _make_list_transactions(store: PersistentSQLiteStore, user_id: str) -> StructuredTool:
    def run(limit: int = 10, type: Optional[Literal["income", "expense"]] = None, period: Optional[Literal["today", "week", "month", "year"]] = None, category: Optional[str] = None) -> str:
        try:
            transactions = store.list_transactions(
                user_id=user_id, limit=limit, type=type, period=period, category=category
            )
            if not transactions:
                return "📭 Nenhuma transação encontrada para os filtros especificados."
            response = "📋 **Transações Recentes**\n\n"
            for trans in transactions:
                emoji = "📈" if trans["type"] == "income" else "📉"
                amount = _format_brl(trans["amount"])
                trans_date = datetime.fromisoformat(trans["date"]).strftime("%d/%m")
                line = f"{emoji} {trans_date} - {amount} | {trans['category']}"
                if trans["description"]:
                    line += f" ({trans['description']})"
                response += f"{line}\n"
            response += f"\n📌 Mostrando {len(transactions)} transação(ões)"
            return response
        except Exception as e:
            return f"❌ Erro ao listar transações: {str(e)}"

    return StructuredTool.from_function(
        name="list_transactions",
        description="Lista transações com filtros opcionais.",
        func=run,
        args_schema=ListTransactionsInput,
    )


def _make_get_category_summary(store: PersistentSQLiteStore, user_id: str) -> StructuredTool:
    def run(period: Literal["today", "week", "month", "year"] = "month") -> str:
        try:
            summary = store.get_category_summary(user_id, period)
            period_text = {
                "today": "Hoje",
                "week": "Última semana",
                "month": "Este mês",
                "year": "Este ano",
            }.get(period, period)
            response = f"📊 **Resumo por Categoria - {period_text}**\n\n"
            if summary["expenses"]:
                response += "📉 **DESPESAS:**\n"
                total_expenses = 0.0
                for category, data in sorted(summary["expenses"].items(), key=lambda x: x[1]["total"], reverse=True):
                    amount = _format_brl(data["total"])
                    response += f"  • {category}: {amount} ({data['count']}x)\n"
                    total_expenses += data["total"]
                response += f"  **Total: {_format_brl(total_expenses)}**\n\n"
            else:
                response += "📉 Nenhuma despesa no período\n\n"
            if summary["income"]:
                response += "📈 **RECEITAS:**\n"
                total_income = 0.0
                for category, data in sorted(summary["income"].items(), key=lambda x: x[1]["total"], reverse=True):
                    amount = _format_brl(data["total"])
                    response += f"  • {category}: {amount} ({data['count']}x)\n"
                    total_income += data["total"]
                response += f"  **Total: {_format_brl(total_income)}**"
            else:
                response += "📈 Nenhuma receita no período"
            return response
        except Exception as e:
            return f"❌ Erro ao obter resumo por categoria: {str(e)}"

    return StructuredTool.from_function(
        name="get_category_summary",
        description="Resumo de despesas e receitas agrupado por categoria.",
        func=run,
        args_schema=GetCategorySummaryInput,
    )


def _make_search_transactions(store: PersistentSQLiteStore, user_id: str) -> StructuredTool:
    def run(search_term: str, limit: int = 5) -> str:
        try:
            all_transactions = store.list_transactions(user_id=user_id, limit=100)
            search_lower = search_term.lower()
            filtered: List[Dict[str, Any]] = []
            for trans in all_transactions:
                if (
                    search_lower in (trans.get("category", "").lower())
                    or search_lower in (trans.get("description", "").lower())
                ):
                    filtered.append(trans)
                    if len(filtered) >= limit:
                        break
            if not filtered:
                return f"🔍 Nenhuma transação encontrada com o termo '{search_term}'"
            response = f"🔍 **Resultados da busca: '{search_term}'**\n\n"
            for trans in filtered:
                emoji = "📈" if trans["type"] == "income" else "📉"
                amount = _format_brl(trans["amount"])
                trans_date = datetime.fromisoformat(trans["date"]).strftime("%d/%m/%Y")
                line = f"{emoji} {trans_date} - {amount}\n   📁 {trans['category']}"
                if trans["description"]:
                    line += f" | {trans['description']}"
                response += f"{line}\n\n"
            response += f"📌 Encontrada(s) {len(filtered)} transação(ões)"
            return response
        except Exception as e:
            return f"❌ Erro na busca: {str(e)}"

    return StructuredTool.from_function(
        name="search_transactions",
        description="Busca transações por termo na descrição ou categoria.",
        func=run,
        args_schema=SearchTransactionsInput,
    )


def create_financial_tools(
    store: PersistentSQLiteStore, user_id: str, thread_id: Optional[str] = None
) -> List[StructuredTool]:
    """
    Cria tools com schemas Pydantic, injetando contexto de `store`, `user_id` e `thread_id` via closures.
    """
    return [
        _make_add_transaction(store, user_id, thread_id),
        _make_get_balance(store, user_id),
        _make_list_transactions(store, user_id),
        _make_get_category_summary(store, user_id),
        _make_search_transactions(store, user_id),
    ]
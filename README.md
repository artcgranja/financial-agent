## 💰 Personal Finance Assistant with LangGraph

An intelligent assistant for personal finance tracking using LangGraph and LLMs, with persistent storage and natural language processing. Tools are implemented with Pydantic schemas and StructuredTool for clear validation and maintainability.

## 🎯 Features

- ✅ **Natural transaction logging** — Add incomes and expenses through natural conversation
- 📊 **Automatic summaries** — View balances by period (day, week, month, year)
- 🏷️ **Smart categorization** — Categories inferred from the description
- 💾 **Full persistence** — Data stored in SQLite with SQLAlchemy ORM
- 🔍 **Search and filters** — Quickly find specific transactions
- 📈 **Category analysis** — Understand where most of your spending goes

## 🚀 Installation

### 1) Clone the repository
```bash
git clone <your-repo>
cd financial-agent
```

### 2) Virtual environment
With venv (pip):
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

Or with uv (optional):
```bash
uv venv
source .venv/bin/activate
```

### 3) Dependencies
```bash
pip install -r requirements.txt
# or with pyproject + uv
# uv sync
```

### 4) Environment variables
Create a `.env` file at the project root with your keys and settings:
```env
# LLM provider and key
# For Claude (Anthropic)
MODEL_NAME=anthropic:claude-sonnet-4-20250514
ANTHROPIC_API_KEY=your_key_here

# OR for GPT (OpenAI)
# MODEL_NAME=openai:gpt-4o-mini
# OPENAI_API_KEY=your_key_here

# Optional
TZ=America/Sao_Paulo
USER_NAME=User
CHECKPOINT_DB=checkpoint.db
STORE_DB=financial_store.db
```

## 💬 Usage

### Interactive mode (Terminal)
```bash
# using Python directly
python scripts/chat.py

# or with uv (recommended)
uv run scripts/chat.py
```

### Conversation examples
```
You: I spent 45 on lunch today
Bot: ✅ Expense recorded! R$ 45.00 in Alimentação

You: I received my salary of 5000
Bot: ✅ Income recorded! R$ 5,000.00 (Salário)

You: How much did I spend this month?
Bot: 📊 This month: Income R$ 5,000, Expenses R$ 1,234, Balance R$ 3,766
```

### Programmatic usage
```python
from app.agent import make_agent
from app.session import make_config, make_context

# Create agent and store
agent, store = make_agent(user_id="my_user")

# Config and context
cfg = make_config(thread_id="session_001", user_id="my_user")
ctx = make_context(user_id="my_user", timezone="America/Sao_Paulo")

# Send a message
result = agent.invoke(
    {"messages": [{"role": "user", "content": "I spent 100 at the supermarket"}]},
    config=cfg,
    context=ctx,
)
print(result)
```

## 📁 Project structure

```text
financial-agent/
├── app/
│   ├── agent.py                # Main LangGraph agent
│   ├── session.py              # Session/stream helpers
│   ├── store.py                # ORM and persistence with SQLAlchemy
│   └── tools/
│       ├── __init__.py
│       └── financial_tools.py  # Tools (StructuredTool + Pydantic)
├── scripts/
│   └── chat.py                 # Interactive CLI
├── requirements.txt            # Dependencies
├── pyproject.toml              # Project configuration (optional)
└── README.md
```

## 🛠️ Tools (Pydantic Schemas)

All tools exposed to the agent use Pydantic schemas for validation.

- **add_transaction**
  - required: `amount: float`, `type: "income"|"expense"`
  - optional: `category: str`, `description: str`, `date_str: str (YYYY-MM-DD or DD/MM/YYYY)`
- **get_balance**
  - `period: "today"|"week"|"month"|"year"|"all"` (default: `month`)
- **list_transactions**
  - `limit: int` (default: 10), `type: "income"|"expense"` (optional), `period` (optional), `category` (optional)
- **get_category_summary**
  - `period: "today"|"week"|"month"|"year"` (default: `month`)
- **search_transactions**
  - `search_term: str`, `limit: int` (default: 5)
- **update_transaction**
  - `transaction_id: int` and optional fields to update: `amount`, `type`, `category`, `description`, `date_str`
- **delete_transaction**
  - `transaction_id: int`
- **clear_user_history**
  - `confirm: "SIM"|"NAO"` — requires `SIM` to proceed

## 🗄️ Database

Two SQLite databases are used:

### `financial_store.db` — Transactions
- Table `transactions`: All financial transactions
- Table `category_mappings`: Keyword mappings

### `checkpoint.db` — LangGraph state
- Maintains conversation context
- Allows resuming sessions

## 🎨 Default categories

### Expenses
- Alimentação, Transporte, Moradia
- Saúde, Educação, Lazer
- Compras, Serviços, Assinaturas

### Income
- Salário, Freelance, Investimentos
- Vendas, Reembolso, Presente

## 🔧 Advanced configuration

### Add new categories
```python
# In store.py, add to CATEGORY_KEYWORDS
'padaria': ('Alimentação', 'expense'),
'bonus': ('Salário', 'income'),
```

### Customize system prompt
```python
# In agent.py, modify SYSTEM_PROMPT
SYSTEM_PROMPT = "Your custom prompt here..."
```

## 📈 Roadmap

- [ ] Web UI with Streamlit/Gradio
- [ ] Charts and visualizations
- [ ] Export to Excel/PDF
- [ ] Goals and budgets
- [ ] Alerts and notifications
- [ ] Bank statement import
- [ ] Multi-user with authentication

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the project
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License.

## 🆘 Support

For questions or issues:
- Open a GitHub issue
- Check LangGraph documentation
- Inspect logs in DEBUG mode
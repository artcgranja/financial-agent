## 💰 Assistente Financeiro Pessoal com LangGraph

Um assistente inteligente para controle de finanças pessoais usando LangGraph e LLMs, com persistência de dados e processamento de linguagem natural. As ferramentas foram refatoradas para usar Pydantic (schemas claros) e StructuredTool, facilitando manutenção e validação de entradas.

## 🎯 Funcionalidades

- ✅ **Registro natural de transações** - Adicione receitas e despesas conversando naturalmente
- 📊 **Resumos automáticos** - Visualize balanços por período (dia, semana, mês, ano)
- 🏷️ **Categorização inteligente** - Categorias inferidas automaticamente pela descrição
- 💾 **Persistência completa** - Dados salvos em SQLite com SQLAlchemy ORM
- 🔍 **Busca e filtros** - Encontre transações específicas facilmente
- 📈 **Análise por categoria** - Entenda onde está gastando mais

## 🚀 Instalação

### 1) Clone o repositório
```bash
git clone <seu-repositorio>
cd financial-agent
```

### 2) Ambiente virtual
Com venv (pip):
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

Ou com uv (opcional):
```bash
uv venv
source .venv/bin/activate
```

### 3) Dependências
```bash
pip install -r requirements.txt
# ou, usando pyproject + uv
# uv sync
```

### 4) Variáveis de ambiente
Crie um arquivo `.env` na raiz com suas chaves e configurações:
```env
# Provedor e chave do LLM
# Para Claude (Anthropic)
MODEL_NAME=anthropic:claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sua_chave_aqui

# OU para GPT (OpenAI)
# MODEL_NAME=openai:gpt-4o-mini
# OPENAI_API_KEY=sua_chave_aqui

# Opcionais
TZ=America/Sao_Paulo
USER_NAME=Usuário
CHECKPOINT_DB=checkpoint.db
STORE_DB=financial_store.db
```

## 💬 Uso

### Modo Interativo (Terminal)
```bash
# usando Python diretamente
python scripts/chat.py

# ou com uv (recomendado)
uv run scripts/chat.py
```

### Exemplo de Conversas
```
Você: Gastei 45 reais no almoço hoje
Bot: ✅ Despesa registrada! R$ 45,00 em Alimentação

Você: Recebi meu salário de 5000
Bot: ✅ Receita registrada! R$ 5.000,00 (Salário)

Você: Quanto gastei este mês?
Bot: 📊 Este mês: Receitas R$ 5.000, Despesas R$ 1.234, Saldo R$ 3.766
```

### Uso Programático
```python
from app.agent import make_agent
from app.session import make_config, make_context

# Criar agente e store
agent, store = make_agent(user_id="meu_usuario")

# Config e contexto
cfg = make_config(thread_id="sessao_001", user_id="meu_usuario")
ctx = make_context(user_id="meu_usuario", timezone="America/Sao_Paulo")

# Enviar mensagem
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Gastei 100 reais no mercado"}]},
    config=cfg,
    context=ctx,
)
print(result)
```

## 📁 Estrutura do Projeto

```text
financial-agent/
├── app/
│   ├── agent.py                # Agente principal LangGraph
│   ├── session.py              # Helpers de sessão/stream
│   ├── store.py                # ORM e persistência com SQLAlchemy
│   └── tools/
│       ├── __init__.py
│       └── financial_tools.py  # Ferramentas (StructuredTool + Pydantic)
├── scripts/
│   └── chat.py                 # CLI interativo
├── requirements.txt            # Dependências
├── pyproject.toml              # Configuração do projeto (opcional)
└── README.md
```

## 🛠️ Ferramentas (Schemas Pydantic)

As tools expostas ao agente possuem validação por schema via Pydantic.

- **add_transaction**
  - required: `amount: float`, `type: "income"|"expense"`
  - optional: `category: str`, `description: str`, `date_str: str (YYYY-MM-DD ou DD/MM/YYYY)`
- **get_balance**
  - `period: "today"|"week"|"month"|"year"|"all"` (default: `month`)
- **list_transactions**
  - `limit: int` (default: 10), `type: "income"|"expense"` (opcional), `period` (opcional), `category` (opcional)
- **get_category_summary**
  - `period: "today"|"week"|"month"|"year"` (default: `month`)
- **search_transactions**
  - `search_term: str`, `limit: int` (default: 5)

## 🗄️ Banco de Dados

O sistema usa duas bases SQLite:

### `financial_store.db` — Transações
- Tabela `transactions`: Todas as transações financeiras
- Tabela `category_mappings`: Mapeamentos de palavras-chave

### `checkpoint.db` — Estado do LangGraph
- Mantém contexto das conversas
- Permite retomar sessões

## 🎨 Categorias Padrão

### Despesas
- Alimentação, Transporte, Moradia
- Saúde, Educação, Lazer
- Compras, Serviços, Assinaturas

### Receitas
- Salário, Freelance, Investimentos
- Vendas, Reembolso, Presente

## 🔧 Configuração Avançada

### Adicionar Novas Categorias
```python
# Em store.py, adicione ao CATEGORY_KEYWORDS
'padaria': ('Alimentação', 'expense'),
'bonus': ('Salário', 'income'),
```

### Customizar System Prompt
```python
# Em agent.py, modifique SYSTEM_PROMPT
SYSTEM_PROMPT = "Seu prompt customizado aqui..."
```

## 📈 Roadmap

- [ ] Interface web com Streamlit/Gradio
- [ ] Gráficos e visualizações
- [ ] Exportação para Excel/PDF
- [ ] Metas e orçamentos
- [ ] Alertas e notificações
- [ ] Importação de extratos bancários
- [ ] Multi-usuário com autenticação

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:
1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT.

## 🆘 Suporte

Para dúvidas ou problemas:
- Abra uma issue no GitHub
- Consulte a documentação do LangGraph
- Verifique os logs em modo DEBUG
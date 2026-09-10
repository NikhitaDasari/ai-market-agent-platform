# AI Market Intelligence & Agent Platform

A Databricks-based AI data engineering project that combines **semantic retrieval, Model Context Protocol (MCP) tools, external APIs, operational data, and agent-driven actions** in one end-to-end workflow.

The project connects market/news context stored in Databricks Lakebase with a custom **FastMCP server**, exposes retrieval and trading tools to Databricks agents, and uses **Alpaca paper trading** for safe, simulated order execution.

> **Tech:** Databricks Apps · Agent Bricks · FastMCP · Lakebase/PostgreSQL · pgvector · Sentence Transformers · Python · Flask · Massive API · Alpaca API

---

## What this project demonstrates

- Building a custom **MCP server** for LLM/agent tool use
- Connecting agents to structured operational data and semantic-search context
- Generating query embeddings with **Sentence Transformers**
- Performing document- and chunk-level similarity search with **pgvector**
- Integrating external REST/API services for market data and paper trading
- Deploying independent backend and dashboard applications with **Databricks Apps**
- Managing credentials through Databricks secret scopes instead of source code
- Separating the agent/tooling layer from the underlying data-ingestion and embedding pipeline

---

## Architecture

```text
                         +---------------------------+
                         |   Databricks Agent Bricks |
                         +-------------+-------------+
                                       |
                                  MCP tool calls
                                       |
                                       v
+----------------+        +---------------------------+        +------------------+
| Massive Market |------->|   FastMCP Server          |------->| Alpaca Markets   |
| Data / Quotes  |        |                           |        | Paper Trading    |
+----------------+        | - market-data tools       |        +------------------+
                          | - watchlist tools          |
                          | - vector_search            |
                          | - account/trading tools    |
                          +-------------+-------------+
                                        |
                                        v
                          +---------------------------+
                          | Databricks Lakebase       |
                          | PostgreSQL + pgvector     |
                          |                           |
                          | watchlist                 |
                          | news documents            |
                          | document embeddings       |
                          | chunk embeddings          |
                          +---------------------------+
                                        |
                                        v
                          +---------------------------+
                          | Databricks Dashboard App |
                          | positions / P&L / orders |
                          +---------------------------+
```

The market-news ingestion, article chunking, and embedding pipeline is implemented in the companion repository:

**[Databricks Lakebase AI Data Pipeline](https://github.com/NikhitaDasari/databricks-lakebase-app-day-2)**

---

## Implemented capabilities

### MCP tool server

`mcp_server/alpaca_mcp_server.py` uses **FastMCP** to expose agent-callable tools including:

- `get_quote`
- `place_trade`
- `get_positions`
- `get_account_summary`
- `get_order_history`
- `get_balance`
- `add_to_watchlist`
- `get_watchlist`
- `remove_from_watchlist`
- `vector_search`
- `get_current_user`

The MCP server is designed to run as a Databricks App and communicate over streamable HTTP.

### Semantic retrieval

The `vector_search` tool accepts a natural-language query, generates an embedding using a Sentence Transformers model, and searches both document-level and chunk-level embeddings stored in Lakebase/PostgreSQL with **pgvector cosine similarity**.

This allows an agent to retrieve relevant market-news context rather than relying only on structured ticker data.

### External API integration

The platform connects to:

- **Massive API** for market quotes and market/news data
- **Alpaca Markets** for hosted paper-trading account data and simulated order execution

Alpaca is used strictly in **paper-trading mode**. No real-money trading is required for this project.

### Databricks Apps

The repository contains two independently deployable Databricks applications:

1. **MCP Server App** — exposes retrieval, watchlist, account, and paper-trading tools to agents.
2. **Dashboard App** — provides a user-facing view of account cash, positions, P/L, and recent paper orders.

### User-aware operations

When deployed through Databricks Apps, the MCP server can read forwarded user identity headers and use the authenticated user when performing watchlist operations.

---

## Repository structure

```text
.
├── mcp_server/
│   ├── alpaca_mcp_server.py   # FastMCP tool server
│   ├── alpaca_broker.py       # Alpaca API adapter
│   ├── massive_broker.py      # Market-data adapter
│   ├── lakebase.py            # Lakebase/PostgreSQL access
│   ├── app.yaml               # Databricks App configuration
│   └── requirements.txt
│
├── dashboard/
│   ├── app.py                 # Flask dashboard
│   ├── alpaca_broker.py
│   ├── templates/
│   ├── app.yaml
│   └── requirements.txt
│
├── setup_secrets.py
├── .env.example
└── README.md
```

---

## Running locally

### MCP server

```bash
cd mcp_server
pip install -r requirements.txt
python alpaca_mcp_server.py
```

The MCP server runs on port `8000` by default.

### Dashboard

```bash
cd dashboard
pip install -r requirements.txt
python app.py
```

The dashboard runs on port `8001` by default.

---

## Databricks deployment

The MCP server and dashboard are deployed as **separate Databricks Apps** using their respective `app.yaml` files.

At a high level:

1. Store Lakebase and Alpaca credentials in Databricks secret scopes.
2. Deploy `mcp_server/` as a Databricks App.
3. Register the deployed endpoint as an external MCP server in Databricks.
4. Attach the MCP tools to a Databricks Agent Bricks agent.
5. Deploy `dashboard/` as a second Databricks App for observing account activity.

Secrets and API credentials are intentionally excluded from the repository.

---

## Related AI data pipeline

This project builds on a separate Databricks data-engineering pipeline that:

- ingests market/news data from an external API,
- stores operational data in Lakebase,
- extracts and chunks article content,
- generates embeddings with Spark and Sentence Transformers,
- persists vectors in PostgreSQL/pgvector, and
- supports semantic retrieval over both full documents and individual passages.

See **[databricks-lakebase-app-day-2](https://github.com/NikhitaDasari/databricks-lakebase-app-day-2)** for that implementation.

---

## Why I built it

I built this project while expanding my data-engineering background into **AI data engineering and agentic applications**. The focus was not just on calling an LLM, but on the data and integration layer behind useful AI systems: ingestion, operational storage, embeddings, retrieval, APIs, tool contracts, identity, and controlled actions.

---

## Safety note

All trading functionality is designed for **Alpaca paper trading only**. It uses simulated funds and is intended for engineering experimentation and demonstration, not investment advice or live-trading automation.

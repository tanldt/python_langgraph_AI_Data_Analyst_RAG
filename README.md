# LangGraph AI Data Analyst + RAG

A runnable learning project that demonstrates a **stateful LangGraph workflow** combining SQLite analytics, lightweight document retrieval, an optional OpenAI LLM, validation, and a Streamlit interface.

> **Important:** The included sales figures and business notes are entirely fictional. This is an educational prototype, not a production-grade analytics system.

## Architecture

```text
START -> Planner -> SQL Agent -> Document Retriever -> Analysis Agent
                                           ^                 |
                                           |                 v
                                      (retry SQL) <- Validator
                                                             |
                                                             v
                                                       Report -> END
```

The graph uses `AgentState` (a `TypedDict`) to pass data between nodes and `MemorySaver` to checkpoint runs within the app process. A validation failure triggers at most two SQL retries. The retrieval step uses **lexical chunk matching** rather than embeddings or a vector database; it demonstrates the RAG pattern but is not semantic vector search.

## Requirements

- Python 3.11 or 3.12
- Windows PowerShell, macOS, or Linux
- An optional OpenAI API key for LLM-powered SQL generation and interpretation

## Setup (Windows PowerShell)

```powershell
cd langgraph_v5
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python scripts_setup.py
streamlit run app/ui.py
```

On macOS/Linux, use `python3 -m venv .venv`, `source .venv/bin/activate`, `cp .env.example .env`, and the same remaining commands.

Open the local Streamlit URL (typically http://localhost:8501).

### Optional: enable OpenAI

Edit `.env`:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

Restart Streamlit. API use may incur costs. Do not commit `.env` or share API keys.

## Example questions

- Compare August and September 2026 revenue and look for explanations in documents.
- Show revenue by category.
- Summarize monthly sales trends.

## Project structure

```text
app/core.py               Graph nodes, state, SQL, retrieval, validation
app/ui.py                 Streamlit user interface
scripts_setup.py          Generate sample SQLite and CSV
 data/docs/business_notes.md  Synthetic document for retrieval
 data/sales.db            Generated database
 data/sales.csv           Generated sample CSV
 tests/test_core.py       Basic safety and graph tests
```

## How it works

1. **Planner:** prepares a brief task plan (LLM if configured).
2. **SQL Agent:** generates a SELECT statement or uses a predefined safe demo query. It reads a SQLite database in read-only mode and limits returned rows.
3. **Retriever:** extracts `.txt`, `.md`, and text-based `.pdf` files from `data/docs`, splits them into overlapping passages, and ranks by shared query terms.
4. **Analysis:** combines SQL rows and retrieved passages. The LLM is instructed to distinguish observations from hypotheses; no-key mode prints a deterministic evidence summary.
5. **Validator:** verifies that SQL returned rows and an analysis exists. This is *not* a full numerical/factual verifier.
6. **Report:** emits a Markdown report with passage identifiers.

## Tests

```bash
python scripts_setup.py
python -m pytest -q
```

## Limitations and next improvements

- The SQL guard is educational and **not** a security boundary. For real deployments use a restricted database account, query parser/AST allowlists, execution timeouts, resource quotas, and human review for sensitive actions.
- The database is read-only; the UI does not upload files. To analyze your own CSV, import it into SQLite with a matching schema or extend the ingestion layer.
- Retrieval is lexical, not vector-based. For true semantic RAG, add embeddings and a vector index such as FAISS/Chroma/pgvector.
- The graph runs sequentially. Parallel SQL and RAG branches are a future enhancement.
- The validator checks completion, not correctness or whether every claim is supported. Add independent numerical checks and evidence verification.
- MemorySaver is process-local and does not provide durable long-term memory. Use a persistent checkpointer for production.
- Never upload confidential company documents to an external model without appropriate authorization and data controls.

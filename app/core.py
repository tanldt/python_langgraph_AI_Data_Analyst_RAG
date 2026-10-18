"""LangGraph V5: bounded SQL + document retrieval + grounded synthesis."""
import os
import re
import sqlite3
from pathlib import Path
from typing import TypedDict

import pandas as pd
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'sales.db'
DOCS = ROOT / 'data' / 'docs'

class AgentState(TypedDict, total=False):
    question: str
    plan: str
    sql: str
    rows: list[dict]
    sources: list[dict]
    analysis: str
    valid: bool
    retries: int
    error: str
    report: str
    trace: list[str]

def llm():
    if not os.getenv('OPENAI_API_KEY'):
        return None
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'), temperature=0)

def ask_llm(system: str, user: str) -> str:
    model = llm()
    if not model:
        return ''
    from langchain_core.messages import SystemMessage, HumanMessage
    return str(model.invoke([SystemMessage(content=system), HumanMessage(content=user)]).content)

def log(state, event):
    return [*state.get('trace', []), event]

def plan(state):
    question = state['question']
    text = ask_llm('You are a data analyst planner. In 2 sentences plan a SQL sales analysis and document lookup. Never claim findings before reading data.', question)
    return {'plan': text or 'Query monthly sales totals and retrieve relevant business notes.', 'trace': log(state, 'Planner: planned SQL + document retrieval')}

def safe_sql(sql: str) -> str:
    sql = sql.strip().rstrip(';').strip()
    if not re.match(r'^SELECT\b', sql, re.I):
        raise ValueError('Only SELECT queries are allowed')
    if ';' in sql or '--' in sql or '/*' in sql or '*/' in sql:
        raise ValueError('Multiple statements and comments are prohibited')
    forbidden = r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|VACUUM|WITH|UNION|INTERSECT|EXCEPT)\b'
    if re.search(forbidden, sql, re.I):
        raise ValueError('Unsafe SQL keyword')
    if not re.search(r'\bFROM\s+sales\b', sql, re.I):
        raise ValueError('Only sales table is allowed')
    return sql

def demo_sql(question):
    q = question.lower()
    if 'product' in q or 'category' in q:
        return 'SELECT category, ROUND(SUM(revenue),2) AS revenue, SUM(tickets) AS tickets FROM sales GROUP BY category ORDER BY revenue DESC LIMIT 50'
    return 'SELECT month, ROUND(SUM(revenue),2) AS revenue, SUM(tickets) AS tickets FROM sales GROUP BY month ORDER BY month LIMIT 50'

def query(state):
    question = state['question']
    default = demo_sql(question)
    raw = ask_llm('Generate ONE SQLite SELECT query only, no markdown. Table sales(month TEXT YYYY-MM, category TEXT, tickets INTEGER, revenue REAL). Only use sales. GROUP BY as appropriate, LIMIT <= 100. No CTEs, no joins, no comments.', question)
    raw = re.sub(r'^```(?:sql)?\s*|\s*```$', '', raw.strip(), flags=re.I)
    sql = default
    error = ''
    if raw:
        try:
            sql = safe_sql(raw)
        except ValueError as exc:
            error = f'Generated SQL rejected ({exc}); used safe fallback.'
    try:
        sql = safe_sql(sql)
        with sqlite3.connect(f'file:{DB}?mode=ro', uri=True) as conn:
            conn.execute('PRAGMA query_only=ON')
            conn.set_progress_handler(lambda: 1, 25000)
            df = pd.read_sql_query(sql, conn)
        rows = df.head(100).to_dict(orient='records')
    except Exception as exc:
        rows = []
        error = str(exc)
    return {'sql': sql, 'rows': rows, 'error': error, 'trace': log(state, f'SQL Agent: {len(rows)} rows')}

def document_text(path: Path) -> str:
    if path.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        return '\n'.join(page.extract_text() or '' for page in PdfReader(str(path)).pages)
    return path.read_text(encoding='utf-8', errors='replace')

def retrieve(state):
    terms = set(re.findall(r'[a-z]{4,}|\d{4}', state['question'].lower()))
    docs = []
    for path in sorted(DOCS.glob('*')):
        if path.suffix.lower() not in ('.txt', '.md', '.pdf'):
            continue
        content = document_text(path)[:40000]
        for index, start in enumerate(range(0, len(content), 850)):
            chunk = content[start:start+1000]
            words = set(re.findall(r'[a-z]{4,}|\d{4}', chunk.lower()))
            score = len(terms & words)
            docs.append({'file': path.name, 'chunk': index, 'text': chunk, 'score': score})
    matches = sorted(docs, key=lambda d: d['score'], reverse=True)
    matches = [x for x in matches if x['score'] > 0][:4]
    return {'sources': matches, 'trace': log(state, f'RAG Retriever: {len(matches)} passages')}

def analyze(state):
    rows = state.get('rows', [])
    context = '\n'.join(f"[{d['file']}#{d['chunk']}] {d['text']}" for d in state.get('sources', []))
    system = ('You are a careful data analyst. Use ONLY supplied rows and document excerpts. '
              'Distinguish numerical observations from hypotheses. Never claim a document proves causation. '
              'Quote numeric values accurately. If insufficient evidence, say so. Cite documents by [filename#chunk].')
    result = ask_llm(system, f"Question: {state['question']}\nSQL: {state.get('sql')}\nRows: {rows}\nDocuments: {context}")
    if not result:
        result = f"SQL returned {len(rows)} rows.\n\n" + '\n'.join(str(row) for row in rows)
        if context:
            result += '\n\nRelevant document excerpts:\n' + context[:2000]
        result += '\n\nNote: This is a deterministic demo summary, not an AI-generated causal explanation.'
    return {'analysis': result, 'trace': log(state, 'Analysis Agent: synthesized evidence')}

def validate(state):
    valid = bool(state.get('rows')) and bool(state.get('analysis', '').strip())
    retries = state.get('retries', 0)
    return {'valid': valid, 'retries': retries + (0 if valid else 1), 'trace': log(state, f'Validator: {"passed" if valid else "failed"}')}

def route(state):
    return 'report' if state['valid'] or state['retries'] >= 2 else 'query'

def report(state):
    status = 'Validated data retrieval' if state.get('valid') else 'Incomplete analysis: review data/query'
    sources = ', '.join(f"{x['file']}#{x['chunk']}" for x in state.get('sources', [])) or 'No relevant passages'
    body = (f"## {status}\n\n**Question:** {state['question']}\n\n"
            f"**SQL:** `{state.get('sql', '')}`\n\n{state.get('analysis', '')}\n\n"
            f"**Retrieved sources:** {sources}\n\n"
            '**Caution:** Correlation or coincident timing does not establish causation.')
    return {'report': body, 'trace': log(state, 'Report Generator: completed')}

def build_graph():
    graph = StateGraph(AgentState)
    for name, fn in [('plan', plan), ('query', query), ('retrieve', retrieve), ('analyze', analyze), ('validate', validate), ('report', report)]:
        graph.add_node(name, fn)
    graph.add_edge(START, 'plan')
    graph.add_edge('plan', 'query')
    graph.add_edge('query', 'retrieve')
    graph.add_edge('retrieve', 'analyze')
    graph.add_edge('analyze', 'validate')
    graph.add_conditional_edges('validate', route, {'query': 'query', 'report': 'report'})
    graph.add_edge('report', END)
    return graph.compile(checkpointer=MemorySaver())

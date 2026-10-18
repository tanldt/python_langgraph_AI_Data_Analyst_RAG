import os
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import streamlit as st
from dotenv import load_dotenv
from app.core import build_graph, DB
load_dotenv()
st.set_page_config(page_title='V5 LangGraph Analyst + RAG', layout='wide')
st.title('V5 — LangGraph AI Data Analyst + RAG')
st.caption('SQLite sales analysis + document retrieval + validation + report')
if 'thread_id' not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if 'graph' not in st.session_state:
    st.session_state.graph = build_graph()
st.info('Mode: ' + ('OpenAI LLM' if os.getenv('OPENAI_API_KEY') else 'No-key deterministic demo'))
question = st.text_input('Ask a question', 'Compare August and September 2026 revenue and look for explanations in documents.')
if st.button('Run analysis', type='primary'):
    if not DB.exists():
        st.error('Sample database missing. Run: python scripts_setup.py')
    else:
        with st.spinner('Running graph...'):
            state = st.session_state.graph.invoke({'question': question, 'retries': 0, 'trace': []}, config={'configurable': {'thread_id': st.session_state.thread_id}})
        st.markdown(state['report'])
        with st.expander('SQL and retrieved data', expanded=True):
            st.code(state.get('sql', ''), language='sql')
            st.dataframe(state.get('rows', []), use_container_width=True)
        with st.expander('RAG passages'):
            for src in state.get('sources', []):
                st.markdown(f"**{src['file']} — chunk {src['chunk']}**")
                st.write(src['text'])
        with st.expander('LangGraph execution trace'):
            st.write('\n'.join(state.get('trace', [])))

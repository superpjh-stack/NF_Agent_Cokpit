"""Offline visual fixture with both roles; never calls OpenAI."""
from pathlib import Path
import runpy
import sys
import streamlit as st
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
st.session_state.messages = [
    {'role': 'user', 'content': '임진감김치 100kg 배합 기준을 확인해줘.', 'created_at': '검증'},
    {'role': 'assistant', 'content': '임진감김치 승인 배합표는 현재 미등록입니다.\n제품 유형과 완제품 100kg 기준인지 먼저 확인해 주세요.\n근거: NF-KB-009 · 데모·미승인', 'created_at': '검증', 'searched_documents': True,
     'sources': ['NF-KB-009.md'], 'data_tools': ['search_knowledge'], 'evidence': [{'filename': 'NF-KB-009.md', 'text': '승인 배합표와 제조조건은 제공되지 않았습니다.'}]}
]
runpy.run_path(str(root/'app.py'), run_name='__main__')

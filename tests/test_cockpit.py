import json
from types import SimpleNamespace as NS

import pytest
from needs_agent import NeedsFoodRepository, NeedsFoodToolRegistry, ManufacturingAgent
from needs_agent.config import change_key
from needs_agent.voice import VoiceService


def test_documents_rules_persist_and_search(tmp_path):
    path = tmp_path / 'demo.db'
    repo = NeedsFoodRepository(path)
    assert len(repo.search_knowledge('임진감김치의 배합표는?')) > 0
    ids = {r['document_id'] for r in repo.browse_table('knowledge_documents', 100)['rows']}
    assert len(ids) == 10
    assert all(r['source_document'] in ids for r in repo.get_rules())
    repo.set_setting('vector_store_id', 'vs_test')
    reopened = NeedsFoodRepository(path)
    assert reopened.get_setting('vector_store_id') == 'vs_test'
    assert reopened.browse_table('knowledge_documents')['total'] == 10
    with pytest.raises(ValueError):
        repo.browse_table('settings')
    with pytest.raises(ValueError):
        repo.browse_table('inventory; DROP TABLE menus')
    with pytest.raises(ValueError):
        repo.browse_table('inventory', -1)
    registry = NeedsFoodToolRegistry(repo)
    assert json.loads(registry.execute('get_rules', {'query': None}))['demo_data'] is True
    assert 'error' in json.loads(registry.execute('get_rules', '[]'))


class Sequence:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return next(self.responses)


def response(i, calls=(), text=''):
    return NS(id=f'r{i}', output=list(calls), output_text=text)


def call(i, name='get_inventory_status', args='{"item":null,"shortage_only":false}'):
    return NS(type='function_call', name=name, arguments=args, call_id=f'c{i}')


def test_round_cap_forces_text(tmp_path):
    sequence = Sequence([response(i, [call(i)]) for i in range(4)] + [response(4, text='확인했습니다.')])
    answer = ManufacturingAgent(NS(responses=sequence), factory_tools=NeedsFoodToolRegistry(NeedsFoodRepository(tmp_path/'d.db'))).ask('재고는?')
    assert sequence.requests[-1]['tool_choice'] == 'none'
    assert len(sequence.requests) == 5
    assert answer.tool_rounds == 4
    assert answer.text
    assert not answer.searched_documents


def test_earlier_search_evidence_survives(tmp_path):
    hit = NS(type='file_search_call', results=[NS(filename='earlier.md', text='초기 근거', score=1)])
    sequence = Sequence([response(1, [hit, call(1)]), response(2, text='답변')])
    answer = ManufacturingAgent(NS(responses=sequence), factory_tools=NeedsFoodToolRegistry(NeedsFoodRepository(tmp_path/'d.db'))).ask('재고는?', vector_store_id='vs')
    assert answer.searched_documents
    assert answer.evidence[0]['text'] == '초기 근거'


def test_procedure_forces_local_retrieval(tmp_path):
    sequence = Sequence([response(1, text='배합표가 미등록입니다.')])
    answer = ManufacturingAgent(NS(responses=sequence), factory_tools=NeedsFoodToolRegistry(NeedsFoodRepository(tmp_path/'d.db'))).ask('임진감김치 배합 기준은?')
    assert answer.searched_documents
    assert any(r['document_id'] == 'NF-KB-009' for r in answer.evidence)
    assert 'search_knowledge' in answer.data_tools
    assert 'NF-KB-009' in sequence.requests[0]['input'][1]['content']


def test_key_change_resets_chain_without_persisting_secret():
    state = {'agent_settings': {'api_key': 'old'}, 'previous_response_id': 'r1'}
    change_key(state, 'new', '세션 재정의')
    assert state['previous_response_id'] is None
    state['previous_response_id'] = 'r2'
    change_key(state, 'new', '세션 재정의')
    assert state['previous_response_id'] == 'r2'


def test_voice_limits_before_network():
    voice = VoiceService(None)
    with pytest.raises(ValueError):
        voice.transcribe(b'')
    with pytest.raises(ValueError):
        voice.speak('x'*3001)


def test_render_and_rerun(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('SQLITE_PATH', str(tmp_path/'ui.db'))
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('OPENAI_API_KEY', '')
    at = AppTest.from_file('app.py', default_timeout=15).run()
    assert not at.exception
    for _ in range(2):
        next(b for b in at.button if b.label == '새 대화').click().run()
        assert not at.exception
        assert len(at.session_state['messages']) == 1
    at.radio(key='question_group').set_value('확인 규칙').run()
    next(s for s in at.selectbox if s.label == '자료 보기').select('공정 DB').run()
    next(s for s in at.selectbox if s.label == '테이블').select('inventory').run()
    assert not at.exception
    next(t for t in at.text_input if t.label == '세션 API 키').set_value('sk-test-only-no-network')
    next(b for b in at.button if b.label == '설정 적용').click().run()
    assert at.session_state['agent_settings']['source'] == '세션 재정의'
    assert not any(t.value == 'sk-test-only-no-network' for t in at.text_input)
    next(b for b in at.button if b.label == '서버 기본 키로 복귀').click().run()
    assert at.session_state['agent_settings']['api_key'] == ''
    assert not at.exception

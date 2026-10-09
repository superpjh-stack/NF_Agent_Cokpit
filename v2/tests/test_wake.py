import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from v2.api import create_app
from v2.compat import NeedsFoodV2Repository
from v2.wake import WAKE_POLICY, calls_agent

CASES=json.loads(Path(__file__).with_name('wake_cases.json').read_text())

@pytest.mark.parametrize('text,expected', CASES)
def test_wake_grammar(text, expected):
    assert calls_agent(text) is expected


def test_another_company_and_regex_aliases():
    policy={'agent_name':'A+B', 'wake_aliases':[' A+B ', ''], 'require_wake_name':True}
    assert calls_agent('A+B, 재고', policy)
    assert not calls_agent('AAAB, 재고', policy)
    assert not calls_agent('니즈, 재고', policy)
    assert calls_agent('송월님, 재고', {'agent_name':'송월','wake_aliases':['송월님'], 'require_wake_name':True})

@pytest.fixture
def client(tmp_path, monkeypatch):
    for key in ('V2_REQUIRE_LOGIN','OPENAI_API_KEY','COCKPIT_ACCESS_TOKEN'):
        monkeypatch.delenv(key, raising=False)
    with TestClient(create_app(NeedsFoodV2Repository(tmp_path/'wake.db'))) as client:
        yield client

@pytest.mark.parametrize('mode',['demo','ai'])
def test_unaddressed_question_does_not_query_or_call_provider(client, monkeypatch, mode):
    lookup=Mock(side_effect=AssertionError('must not query'))
    provider=Mock(side_effect=AssertionError('must not call AI'))
    monkeypatch.setattr(client.app.state.repo,'lot_trace',lookup)
    monkeypatch.setattr('v2.api.ManufacturingAgent.ask',provider)
    result=client.post('/api/chat',json={'question':'오늘 재고 알려줘','mode':mode,'lot_id':'invalid'}).json()
    assert result['ignored'] is True
    assert result['text']=='' and result['records']==[] and result['evidence']==[]
    lookup.assert_not_called();provider.assert_not_called()


def test_every_followup_needs_address_and_suggestions_work(client):
    workspace=client.get('/api/workspace').json()
    assert workspace['meta']['wake']==WAKE_POLICY
    for questions in workspace['questions'].values():
        assert all(calls_agent(question) for question in questions)
    answer=client.post('/api/chat',json={'question':'니즈, 생산 현황을 알려줘'}).json()
    assert answer['records'] and not answer.get('ignored')
    assert client.post('/api/chat',json={'question':'그럼 재고는?'}).json()['ignored'] is True


def test_realtime_disables_automatic_response(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-only')
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN','test-code')
    captured={}
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            captured.update(json.loads(kwargs['files']['session'][1]))
            return httpx.Response(200,text='fake-sdp')
    monkeypatch.setattr('v2.api.httpx.AsyncClient',FakeClient)
    result=client.post('/api/realtime/session',content='fake-offer',headers={'Content-Type':'application/sdp','Authorization':'Bearer test-code'})
    assert result.status_code==200
    detection=captured['audio']['input']['turn_detection']
    assert detection['create_response'] is False and detection['interrupt_response'] is False
    assert '니즈' in captured['instructions']

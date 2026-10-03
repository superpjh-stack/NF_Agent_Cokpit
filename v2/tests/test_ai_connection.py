"""Connection failures must explain what the operator can actually resolve."""
import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AuthenticationError, RateLimitError
from v2.api import create_app
from v2.compat import NeedsFoodV2Repository


@pytest.mark.parametrize('exception,code,status,expected', [
    (RateLimitError, 'credit_balance_exhausted', 429, '크레딧'),
    (RateLimitError, 'insufficient_quota', 429, '크레딧'),
    (RateLimitError, 'rate_limit_exceeded', 429, '잠시 기다린'),
    (AuthenticationError, 'invalid_api_key', 503, '키 인증에 실패'),
])
def test_ai_connection_errors_are_actionable(tmp_path, monkeypatch, exception, code, status, expected):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key-not-a-real-credential')
    monkeypatch.delenv('V2_REQUIRE_LOGIN', raising=False)
    response = httpx.Response(401 if exception is AuthenticationError else 429,
                             request=httpx.Request('POST', 'https://api.openai.com/v1/responses'))
    def fail(*args, **kwargs):
        raise exception('provider message must not be displayed', response=response,
                        body={'code': code, 'message': 'private provider detail'})
    monkeypatch.setattr('v2.api.ManufacturingAgent.ask', fail)
    with TestClient(create_app(NeedsFoodV2Repository(tmp_path / 'connection.db'))) as client:
        # Repeated errors must not exhaust the server's concurrent request slots.
        for _ in range(4):
            result = client.post('/api/chat', json={'question': '생산 현황을 알려줘', 'mode': 'ai'})
            assert result.status_code == status
            assert expected in result.json()['detail']
            assert 'private provider detail' not in result.text
            assert 'test-key' not in result.text


def test_local_realtime_session_accepts_server_managed_key_without_browser_code(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'server-key-not-a-real-credential')
    monkeypatch.setenv('V2_LOCAL_AI_NO_TOKEN', '1')
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)

    class FakeAsyncClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            assert url == 'https://api.openai.com/v1/realtime/calls'
            assert kwargs['headers']['Authorization'].startswith('Bearer server-key')
            return httpx.Response(200, text='answer-sdp')

    monkeypatch.setattr('v2.api.httpx.AsyncClient', FakeAsyncClient)
    with TestClient(create_app(NeedsFoodV2Repository(tmp_path / 'realtime.db'))) as client:
        result = client.post('/api/realtime/session', content='offer-sdp',
                             headers={'Content-Type':'application/sdp'})
        assert result.status_code == 200
        assert result.text == 'answer-sdp'
        assert 'server-key' not in result.text


def test_realtime_credit_exhaustion_is_explained(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'server-key-not-a-real-credential')

    class FakeAsyncClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            return httpx.Response(429, json={'error': {'code':'credit_balance_exhausted'}},
                                  request=httpx.Request('POST', url))

    monkeypatch.setattr('v2.api.httpx.AsyncClient', FakeAsyncClient)
    with TestClient(create_app(NeedsFoodV2Repository(tmp_path / 'voice-credit.db'))) as client:
        result = client.post('/api/realtime/session', content='offer-sdp',
                             headers={'Content-Type':'application/sdp'})
        assert result.status_code == 429
        assert '크레딧' in result.json()['detail']

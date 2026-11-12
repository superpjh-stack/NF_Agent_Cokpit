from __future__ import annotations

import os
import json
import re
import secrets
import hashlib
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from threading import BoundedSemaphore

import httpx
from openai import AuthenticationError, RateLimitError, OpenAIError

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from v2.compat import NeedsFoodV2Repository as NeedsFoodRepository, NeedsFoodV2ToolRegistry as NeedsFoodToolRegistry, ManufacturingAgent, QUESTION_GROUPS, PostgresRepository, create_repository, lot_snapshot
from needs_agent.config import model_name

DEFAULT_MODEL = model_name()
from v2.compound import analyze, resolve_lot
from v2.wake import WAKE_POLICY, calls_agent, addressed_question
from v2.domain import demo_answer, EvidenceRegistry
from v2.chat_service import run_chat
from v2 import reports
from v2.studio import StudioRequest,build_studio
from v2.metrics import create_tables, install_metrics
from v2.work import WorkStore, install_work, stamp

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


class Question(BaseModel):
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)
    question: str = Field(min_length=1, max_length=2000)
    lot_id: str | None = Field(default=None, max_length=80)
    work_id: str | None = Field(default=None, max_length=80)
    mode: str = Field(default='demo', pattern='^(demo|ai)$')


class Speech(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class RealtimeToolCall(BaseModel):
    name: str = Field(pattern='^(analyze_manufacturing_question|search_knowledge|get_rules|get_daily_briefing|get_production_delays|get_inventory_status|get_quality_summary|get_batch_trace|get_cooking_conditions|get_recipe_cost|get_kimchi_readiness|calculate_kimchi_materials|get_kimchi_lot_trace)$')
    arguments: dict = Field(default_factory=dict)


def create_app(repository=None, static_dir: Path | None = None):
    provided_repository = repository

    @asynccontextmanager
    async def lifespan(app):
        selected_repository = provided_repository or create_repository(os.getenv('V2_SQLITE_PATH', str(ROOT / 'data/needs_food_v2_demo.db')))
        if not isinstance(selected_repository, NeedsFoodRepository):
            selected_repository = NeedsFoodRepository(selected_repository)
        app.state.repo = selected_repository
        app.state.work = WorkStore(app.state.repo)
        create_tables(app.state.repo)
        yield

    app = FastAPI(title='Needs Food Operations API', version='3.0.0', lifespan=lifespan)
    capacity = BoundedSemaphore(3)
    voice_capacity = BoundedSemaphore(3)
    install_work(app)
    install_metrics(app)
    reports.install(app)

    @app.middleware('http')
    async def boundaries(request, call_next):
        if request.url.path.startswith('/api/'):
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                origin = request.headers.get('origin')
                expected = str(request.base_url).rstrip('/')
                allowed_origins = {expected}
                allowed_origins.update(o.strip().rstrip("/") for o in os.getenv("NEEDSFOOD_PUBLIC_ORIGINS", "").split(",") if o.strip())
                if request.url.hostname in {'127.0.0.1', 'localhost'}:
                    allowed_origins.update({'http://127.0.0.1:5173', 'http://localhost:5173'})
                if request.headers.get('sec-fetch-site') == 'cross-site' or (origin and origin not in allowed_origins):
                    return JSONResponse({'detail': '동일 출처에서 다시 요청하세요.'}, status_code=403)
            public = ('/api/health', '/api/auth/login', '/api/auth/me')
            if os.getenv('V2_REQUIRE_LOGIN') == '1' and request.url.path not in public:
                try:
                    app.state.work.user(request)
                except HTTPException as exc:
                    return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)
        response = await call_next(request)
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    def local_ai_allowed(request: Request):
        return (
            request.client is not None
            and request.client.host in {'127.0.0.1', '::1', 'testclient'}
            and request.url.hostname in {'127.0.0.1', 'localhost', 'testserver'}
        )

    def require_ai(authorization, request: Request):
        require_ai_key(authorization, request)
        from openai import OpenAI
        return OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=35, max_retries=1)

    def require_ai_key(authorization, request: Request):
        expected = os.getenv('COCKPIT_ACCESS_TOKEN', '')
        if not os.getenv('OPENAI_API_KEY', ''):
            raise HTTPException(503, '서버에 OpenAI API 키를 설정해야 합니다.')
        if local_ai_allowed(request):
            return os.environ['OPENAI_API_KEY']
        if not expected:
            raise HTTPException(503, '외부 접속에서는 AI 접근 코드를 설정해야 합니다.')
        if not secrets.compare_digest(authorization or '', 'Bearer ' + expected):
            raise HTTPException(401, '설정에서 올바른 AI 접근 코드를 입력해 주세요.')
        return os.environ['OPENAI_API_KEY']

    def realtime_context(lot_id: str | None):
        repo = app.state.repo
        if lot_id:
            if not repo.lot_trace(lot_id):
                raise HTTPException(404, '선택한 LOT를 찾을 수 없습니다.')
            context = lot_snapshot(repo, lot_id)
        else:
            context = {
                'dashboard': repo.dashboard(),
                'fermentation': repo.fermentation_status(None),
                'ccp': repo.ccp_deviations(None),
                'inventory': repo.inventory_status(None, False),
                'shipments': repo.shipment_readiness(None),
            }
        return json.dumps(context, ensure_ascii=False, default=str)[:24000]

    @app.post('/api/realtime/session')
    async def realtime_session(request: Request, lot_id: str | None = Query(default=None, max_length=80), authorization: str | None = Header(default=None)):
        api_key = require_ai_key(authorization, request)
        if request.headers.get('content-type', '').split(';')[0] != 'application/sdp':
            raise HTTPException(415, 'WebRTC 연결 정보가 필요합니다.')
        offer = await request.body()
        if not offer or len(offer) > 100_000:
            raise HTTPException(413, 'WebRTC 연결 정보가 올바르지 않습니다.')
        user = app.state.work.user(request, False)
        identity = user['id'] if user else 'anonymous'
        safety_id = hashlib.sha256(f'needsfood:{identity}'.encode()).hexdigest()
        instructions = (
            '당신은 니즈푸드 제조 현장의 한국어 음성 업무 도우미다. 짧고 자연스러운 존댓말로 답한다. '
            f"당신의 호출명은 {WAKE_POLICY['agent_name']}다. 호출명 없이 질문과 후속 질문에 답한다. 핵심부터 답한다. "
            '아래 제공된 조회 전용 자료는 회사 기록 질문에만 사용한다. 일반 지식 질문은 알고 있는 내용으로 답한다. '
            '생산·품질·재고·배치·조리조건 질문은 반드시 아래 제공된 니즈푸드 읽기 전용 도구를 호출한다. '
            '회사 기록에 없는 값은 반드시 미확인이라고 말하고 추측하지 않는다. 수치에는 단위와 KST 시각을 붙인다. 출하 승인, CCP 처분, 공정 변경을 결정하거나 실행하지 않는다. '
            'LOT·수치·상태는 잘못 들었을 수 있으므로 중요한 식별자는 짧게 재확인한다. 답변은 보통 3문장 이내로 한다.\n'
            f'현재 선택 LOT: {lot_id or "전체 기록"}\n조회 자료: {realtime_context(lot_id)}'
        )
        registry = NeedsFoodToolRegistry(app.state.repo)
        realtime_tools = [{'type':'function','name':'analyze_manufacturing_question','description':'니즈푸드 질문 전체를 LangGraph로 조회·분석한다.','parameters':{'type':'object','properties':{'question':{'type':'string'},'lot_id':{'type':['string','null']}},'required':['question','lot_id'],'additionalProperties':False}}]
        instructions += '\n제조 질문은 analyze_manufacturing_question으로 조회하고 반환된 voice_summary를 읽으세요. 근거 없는 값을 만들지 마세요.'
        session = {
            'type': 'realtime',
            'model': os.getenv('OPENAI_REALTIME_MODEL', 'gpt-realtime-2.1'),
            'instructions': instructions,
            'output_modalities': ['audio'],
            'tools': realtime_tools,
            'tool_choice': 'auto',
            'audio': {
                'input': {
                    'transcription': {'model': 'gpt-4o-mini-transcribe', 'language': 'ko'},
                    'noise_reduction': {'type': 'near_field'},
                    'turn_detection': {'type': 'semantic_vad', 'eagerness': 'auto', 'create_response': False, 'interrupt_response': True},
                },
                'output': {'voice': os.getenv('OPENAI_REALTIME_VOICE', 'marin')},
            },
        }
        files = {'sdp': (None, offer.decode('utf-8'), 'application/sdp'), 'session': (None, json.dumps(session, ensure_ascii=False), 'application/json')}
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                upstream = await client.post('https://api.openai.com/v1/realtime/calls', headers={'Authorization': f'Bearer {api_key}', 'OpenAI-Safety-Identifier': safety_id}, files=files)
        except httpx.HTTPError as exc:
            raise HTTPException(502, '실시간 음성 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.') from exc
        if upstream.status_code == 429:
            try:
                provider_error = upstream.json().get('error', {})
                code = provider_error.get('code')
            except (ValueError, AttributeError):
                code = None
            if code in {'credit_balance_exhausted', 'insufficient_quota', 'billing_hard_limit_reached'}:
                raise HTTPException(429, 'OpenAI API 크레딧이 소진되었습니다. 크레딧을 충전한 뒤 실시간 음성을 다시 시작해 주세요.')
            raise HTTPException(429, '실시간 음성 요청이 몰리고 있습니다. 잠시 후 다시 시도해 주세요.')
        if upstream.status_code in {401, 403}:
            raise HTTPException(503, '실시간 음성 모델의 키 권한을 확인해 주세요.')
        if upstream.status_code >= 400:
            raise HTTPException(502, '실시간 음성 세션을 만들지 못했습니다. 모델 사용 권한과 서버 설정을 확인해 주세요.')
        return Response(upstream.text, media_type='application/sdp')

    @app.post('/api/realtime/tool')
    def realtime_tool(body: RealtimeToolCall, request: Request, authorization: str | None = Header(default=None)):
        require_ai_key(authorization, request)
        if body.name == 'analyze_manufacturing_question':
            answer = chat(Question(**{**body.arguments, 'mode':'ai'}), request, Response(), authorization)
            return {'output':json.dumps(answer,ensure_ascii=False)}
        registry = NeedsFoodToolRegistry(app.state.repo)
        output = registry.execute(body.name, body.arguments)
        return {'output': output}

    @app.get('/api/health')
    def health():
        app.state.repo.dashboard()
        return {'status': 'ok', 'version': '3.0.0'}

    @app.get('/api/workspace')
    def workspace(request: Request):
        repo = app.state.repo
        local_dev_ai = bool(os.getenv('OPENAI_API_KEY')) and local_ai_allowed(request)
        return {'kpi': repo.dashboard(), 'lots': repo.all_lots(), 'fermentation': repo.fermentation_status(None), 'ccp': repo.ccp_deviations(None), 'inventory': repo.inventory_status(None, False), 'shipments': repo.shipment_readiness(None), 'rules': repo.get_rules(), 'tables': repo.table_inventory(), 'questions': {group: [addressed_question(q) for q in questions] for group, questions in QUESTION_GROUPS.items()}, 'meta': {'wake': WAKE_POLICY, 'company': '니즈푸드 제조 AI', 'version': '3.0', 'demo_data': True, 'as_of': '2026-09-03', 'backend': 'PostgreSQL + pgvector' if isinstance(repo, PostgresRepository) else 'SQLite', 'ai_configured': bool(os.getenv('OPENAI_API_KEY') and (os.getenv('COCKPIT_ACCESS_TOKEN') or local_dev_ai)), 'local_dev_ai': local_dev_ai, 'model': os.getenv('OPENAI_MODEL') or DEFAULT_MODEL, 'retrieved_at': stamp()}}

    @app.get('/api/lots/{lot_id}')
    def detail(lot_id: str):
        result = lot_snapshot(app.state.repo, lot_id)
        if not result['lot']:
            raise HTTPException(404, 'LOT를 찾을 수 없습니다.')
        result['measurements'] = [row for row in app.state.repo.process_measurements(None) if row['lot_id'] in {r['lot_id'] for r in result['trace']}]
        return result

    @app.get('/api/documents')
    def documents(q: str = Query(default='', max_length=200)):
        repo = app.state.repo
        matches = {d['document_id'] for d in repo.search_knowledge(q)} if q.strip() else None
        return [{k: v for k, v in d.items() if k not in {'embedding', 'embedding_model'}} for d in repo.knowledge_documents() if matches is None or d['document_id'] in matches]

    @app.get('/api/tables/{table}')
    def table_records(table: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        try:
            return app.state.repo.table_records(table, limit, offset)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post('/api/connection/check')
    def connection_check(request:Request,authorization:str|None=Header(default=None)):
        if not capacity.acquire(blocking=False):raise HTTPException(429,'다른 요청을 처리 중입니다.')
        try:
            with require_ai(authorization,request) as client:
                result=client.with_options(timeout=20,max_retries=0).responses.create(model=os.getenv('OPENAI_MODEL') or DEFAULT_MODEL,input='연결 확인입니다. OK만 답하세요.',max_output_tokens=32)
                if not result.output_text:raise HTTPException(502,'모델이 빈 응답을 반환했습니다.')
                return {'status':'ok','model':result.model,'requested_model':os.getenv('OPENAI_MODEL') or DEFAULT_MODEL,'checked_at':stamp()}
        except HTTPException:raise
        except AuthenticationError as exc:raise HTTPException(503,'서버 API 키 인증에 실패했습니다.') from exc
        except RateLimitError as exc:raise HTTPException(429,'AI 사용 한도 또는 요청 제한을 확인하세요.') from exc
        except OpenAIError as exc:raise HTTPException(502,'모델 연결에 실패했습니다. 서버 모델 ID와 사용 권한을 확인하세요.') from exc
        finally:capacity.release()

    @app.post('/api/studio')
    def studio(body:StudioRequest,request:Request,authorization:str|None=Header(default=None)):
        try:
            if body.use_ai and body.mode=='ideas':
                if not capacity.acquire(blocking=False):raise HTTPException(429,'다른 요청을 처리 중입니다.')
                try:
                    with require_ai(authorization,request) as client:return build_studio(app.state.repo,body,client,os.getenv('OPENAI_MODEL') or DEFAULT_MODEL)
                finally:capacity.release()
            return build_studio(app.state.repo,body)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        except OpenAIError as exc:raise HTTPException(502,'AI 연결·사용 한도를 확인하세요.') from exc

    @app.post('/api/chat/reset')
    def reset(request: Request, response: Response):
        response.delete_cookie('needsfood_session', path='/api')
        return {'status': 'ok'}

    @app.post('/api/chat')
    def chat(body: Question, request: Request, response: Response, authorization: str | None = Header(default=None)):
        return run_chat(body, request, app.state.repo, app.state.work, require_ai, capacity, authorization)

    @app.post('/api/voice/transcribe')
    def transcribe(request: Request, file: UploadFile, authorization: str | None = Header(default=None)):
        client = require_ai(authorization, request)
        if not voice_capacity.acquire(blocking=False):
            client.close()
            raise HTTPException(429, '음성 처리 중입니다. 잠시 후 다시 시도하세요.')
        try:
            if not (file.content_type or '').startswith(('audio/', 'video/webm', 'video/mp4')):
                raise HTTPException(415, '지원되는 음성 파일을 선택하세요.')
            content = file.file.read(20 * 1024 * 1024 + 1)
            if not content or len(content) > 20 * 1024 * 1024:
                raise HTTPException(413, '녹음 파일은 20MB 이하로 선택해 주세요.')
            result = client.audio.transcriptions.create(model='gpt-4o-mini-transcribe', file=(Path(file.filename or 'recording.webm').name, content, file.content_type), language='ko')
            return {'text': result.text}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, '음성 변환에 실패했습니다. 텍스트 질문을 이용해 주세요.') from exc
        finally:
            client.close()
            voice_capacity.release()

    @app.post('/api/voice/speak')
    def speak(body: Speech, request: Request, authorization: str | None = Header(default=None)):
        client = require_ai(authorization, request)
        if not voice_capacity.acquire(blocking=False):
            client.close()
            raise HTTPException(429, '음성 처리 중입니다. 잠시 후 다시 시도하세요.')
        try:
            from needs_agent.voice import VoiceService
            return Response(VoiceService(client).speak(body.text), media_type='audio/mpeg')
        except Exception as exc:
            raise HTTPException(502, '음성 재생 파일을 만들지 못했습니다.') from exc
        finally:
            client.close()
            voice_capacity.release()

    dist = static_dir or ROOT / 'v2/web/dist'
    if dist.exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/work/{work_id}')
        def work_entry(work_id: str):
            return FileResponse(dist / 'index.html')

        @app.get('/')
        def index():
            return FileResponse(dist / 'index.html')
    return app


app = create_app()

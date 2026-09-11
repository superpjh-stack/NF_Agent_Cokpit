from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

import streamlit as st
from openai import OpenAI
from needs_agent.config import model_name, change_key, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS
from needs_agent.voice import VoiceService

STYLE = """<style>
.block-container{padding-top:1.4rem;max-width:1680px;padding-bottom:2rem}
.stApp{background:#f2f3f4;color:#20262c}h1,h2,h3{letter-spacing:-.025em}
.kicker{font-size:12px;letter-spacing:.14em;font-weight:700;color:#a54a16}.subtitle{color:#55616b;font-size:14px;margin-bottom:18px}
[data-testid=stMetric]{border-top:2px solid #c4cbd0;padding:12px 8px;background:#fff}
[data-testid=stMetricLabel]{color:#52606b}[data-testid=stMetricValue]{font-variant-numeric:tabular-nums;font-size:27px}
button{min-height:44px!important;border-radius:5px!important}div.stButton>button{text-align:left;justify-content:flex-start;white-space:normal}
.st-key-chat_console{background:#242b31;border-top:3px solid #d86d30;border-radius:6px;padding:18px;color:#f5f7f9;min-width:0}
.st-key-chat_history{height:500px;overflow-y:auto;overflow-x:hidden}
.st-key-chat_console h3,.st-key-chat_console [data-testid=stCaptionContainer]{color:#e3e8ec}
.st-key-chat_console [data-testid=stChatMessage]{background:#f8fafb;color:#20262c;border-radius:5px;padding:12px;margin-bottom:12px}
.st-key-chat_console [data-testid=stChatMessage]:has([data-testid=stChatMessageAvatarUser]){background:#f7e6d9;border-left:3px solid #cf692f}
.st-key-chat_console [data-testid=stChatMessage] [data-testid=stCaptionContainer]{color:#53616b}
.st-key-chat_console [data-testid=stChatMessage] p{color:#20262c;line-height:1.7}
.st-key-chat_console button{color:#20262c!important;background:#f8fafb}
.st-key-chat_console [data-testid=stAlert]{background:#e8edf0;color:#20262c}
.st-key-chat_console [data-testid=stAlert] p{color:#20262c}
.st-key-chat_console [data-testid=stExpander] [data-testid=stCaptionContainer]{color:#53616b}
.st-key-context_panel h1{font-size:1.35rem}
.st-key-recommendations,.st-key-context_panel{background:#fff;padding:16px;border:1px solid #d9dfe3;border-radius:6px}
.st-key-layout [data-testid=stColumn]{min-width:0}.st-key-chat_console [data-testid=stExpander]{background:#fff;color:#20262c}
.st-key-chat_console [data-testid=stChatInput]{color:#20262c}.st-key-jumpnav{display:none}
@media(min-width:641px) and (max-width:1100px){
.st-key-layout [data-testid=stHorizontalBlock]:has(.st-key-chat_console){flex-direction:column}
.st-key-layout [data-testid=stColumn]:has(.st-key-chat_console),.st-key-layout [data-testid=stColumn]:has(.st-key-context_panel),.st-key-layout [data-testid=stColumn]:has(.st-key-recommendations){width:100%!important;flex:1 1 auto!important}
.st-key-layout [data-testid=stColumn]:has(.st-key-chat_console){order:-1}
.st-key-jumpnav{display:block;position:sticky;top:3rem;background:#fff;z-index:10;padding:8px}
}
@media(max-width:640px){
.block-container{padding:1rem .65rem;min-height:100dvh;max-width:100%}
.st-key-kpis,.st-key-recommendations,.st-key-context_panel,.st-key-voice_panel,.st-key-page_intro{display:none!important}
.st-key-layout [data-testid=stHorizontalBlock]:has(.st-key-chat_console){display:block}
.st-key-layout [data-testid=stColumn]:has(.st-key-chat_console){width:100%!important;min-width:0;flex:1 1 100%!important}
.st-key-layout [data-testid=stColumn]:has(.st-key-recommendations),.st-key-layout [data-testid=stColumn]:has(.st-key-context_panel){display:none!important}
.st-key-chat_console{padding:10px;min-height:calc(100dvh - 100px)}
.st-key-chat_console [class*=st-key-voice_play_]{display:none!important}
.st-key-chat_console h3{font-size:1.15rem}
.st-key-chat_history{height:calc(100dvh - 550px)!important;min-height:100px}
.st-key-chat_console [data-testid=stChatInput]{position:sticky;bottom:env(safe-area-inset-bottom,0);z-index:5}
[data-testid=stChatMessage]{padding:8px!important}p{overflow-wrap:anywhere}
}
</style>"""


def render_cockpit(*, base_dir: Path, page_title: str, icon: str, title: str, subtitle: str,
                   repository: Any, registry: Any, agent_factory: Callable[[Any, str, Any], Any],
                   question_groups: dict[str, list[str]], welcome_message: dict[str, Any],
                   timestamp: Callable[[], str], history_fn: Callable[..., list[dict[str, str]]],
                   metrics: list[tuple[str, str]], entity_label: str, entity_ids: list[str],
                   snapshot_builder: Callable[[str], dict[str, Any]], knowledge_label: str,
                   knowledge_base_name: str, source_label: str, chat_placeholder: str,
                   safety_note: str) -> None:
    st.set_page_config(page_title=page_title, page_icon=icon, layout="wide", initial_sidebar_state="collapsed")
    st.markdown(STYLE, unsafe_allow_html=True)
    server_key = os.getenv("OPENAI_API_KEY", "")
    defaults = {"messages": [welcome_message.copy()], "vector_store_id": repository.get_setting("vector_store_id"),
                "uploaded_names": [], "previous_response_id": None, "pending_question": None,
                "question_group": next(iter(question_groups)), "voice_draft": "", "voice_digest": None,
                "speech_cache": {}, "agent_settings": {"api_key": server_key, "source": "서버 기본값", "model": model_name(), "max_results": 6}}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    settings = st.session_state.agent_settings

    def apply_settings():
        override = st.session_state.get("override_key", "").strip()
        if override:
            change_key(st.session_state, override, "세션 재정의")
        settings.update(model=st.session_state["model_edit"].strip() or model_name(),
                        max_results=st.session_state["depth_edit"])
        st.session_state.override_key = ""

    def queue(question):
        st.session_state.pending_question = question

    def reset():
        st.session_state.messages = [welcome_message.copy()]
        st.session_state.previous_response_id = None
        st.session_state.pending_question = None
        st.session_state.voice_draft = ""
        st.session_state.speech_cache = {}
        # Keep audio widget identity and digest; old recordings are not retranscribed.

    with st.sidebar:
        st.header("Agent 설정")
        tail = "••••" + settings["api_key"][-4:] if len(settings["api_key"]) > 4 else "설정됨"
        st.caption(f"{settings['source']} · {tail}" if settings["api_key"] else "API 키 없음 · 문서와 DB 조회 가능")
        with st.expander("키·모델·검색 설정", expanded=False):
            with st.form("settings_form", clear_on_submit=True):
                st.text_input("세션 API 키", key="override_key", type="password", help="빈칸은 현재 키 유지. 서버 키를 입력창에 표시하지 않습니다.")
                st.text_input("모델", key="model_edit", value=settings["model"])
                st.slider("문서 검색 개수", 1, 20, settings["max_results"], key="depth_edit")
                st.form_submit_button("설정 적용", on_click=apply_settings)
            if st.button("서버 기본 키로 복귀"):
                change_key(st.session_state, server_key, "서버 기본값")
                st.session_state.vector_store_id = repository.get_setting("vector_store_id")
                st.rerun()
        st.caption(safety_note)

    client = OpenAI(api_key=settings["api_key"], timeout=35.0, max_retries=1) if settings["api_key"] else None
    agent = agent_factory(client, settings["model"], registry) if client else None
    voice = VoiceService(client) if client else None
    with st.sidebar:
        with st.expander("지식문서 업로드"):
            st.caption("인덱싱을 누르면 선택 문서를 설정된 OpenAI API로 전송합니다.")
            uploads = st.file_uploader(knowledge_label, accept_multiple_files=True, type=["pdf", "docx", "txt", "md", "csv"])
            if st.button("문서 인덱싱", disabled=not uploads or not agent):
                try:
                    if not st.session_state.vector_store_id:
                        st.session_state.vector_store_id = agent.create_knowledge_base(knowledge_base_name)
                        if settings["source"] == "서버 기본값":
                            repository.set_setting("vector_store_id", st.session_state.vector_store_id)
                    with st.spinner("문서를 연결하고 있습니다…"):
                        for uploaded in uploads:
                            if uploaded.size > 20 * 1024 * 1024:
                                raise ValueError("문서는 20MB 이하로 나누어 주세요.")
                            with tempfile.TemporaryDirectory() as directory:
                                path = Path(directory) / Path(uploaded.name).name
                                path.write_bytes(uploaded.getvalue())
                                agent.add_file(st.session_state.vector_store_id, path)
                            if uploaded.name not in st.session_state.uploaded_names:
                                st.session_state.uploaded_names.append(uploaded.name)
                    st.success("문서 연결 완료")
                except Exception:
                    st.error("문서 연결에 실패했습니다. 키 권한·파일 크기·네트워크를 확인하세요.")
            st.caption("연결: " + (", ".join(st.session_state.uploaded_names) or "이번 세션 업로드 없음"))

    with st.container(key="page_intro"):
        st.markdown('<div class="kicker">NEEDS FOOD / MANUFACTURING INTELLIGENCE</div>', unsafe_allow_html=True)
        st.title(title)
        st.markdown(f'<div class="subtitle">{subtitle}</div>', unsafe_allow_html=True)
        st.caption(f"데모 기준일 2026-09-03 · {repository.backend} · 조회·권고 전용")
    with st.container(key="kpis"):
        cols = st.columns(len(metrics))
        for column, (label, value) in zip(cols, metrics):
            column.metric(label, value)
    with st.container(key="jumpnav"):
        st.markdown("[대화](#agent-console) · [추천 질문](#recommendations) · [근거 자료](#data-panel)")
    with st.container(key="layout"):
        left, chat, context = st.columns([1.05, 2.35, 1.45], gap="medium")
    with left, st.container(key="recommendations"):
        st.markdown('<span id="recommendations"></span>', unsafe_allow_html=True)
        st.subheader("추천 질문")
        group = st.radio("근거 출처", list(question_groups), key="question_group", horizontal=True)
        for i, question in enumerate(question_groups[group]):
            st.button(question, key=f"suggestion_{group}_{i}", width="stretch", on_click=queue, args=(question,))
        with st.expander("최근 질문"):
            history = history_fn(st.session_state.messages)
            if not history:
                st.caption("아직 질문이 없습니다.")
            for i, item in enumerate(history):
                st.button(item["content"][:50], key=f"history_{i}", on_click=queue, args=(item["content"],), width="stretch")

    with context, st.container(key="context_panel"):
        st.markdown('<span id="data-panel"></span>', unsafe_allow_html=True)
        st.subheader("근거 자료")
        panel = st.selectbox("자료 보기", ["지식문서", "공정 DB", "확인 규칙", "배치 상황"])
        if panel == "지식문서":
            query = st.text_input("문서 검색", placeholder="임진감김치, 배합, 검식…")
            docs = repository.search_knowledge(query, 10) if query.strip() else repository.browse_table("knowledge_documents", 100)["rows"]
            if docs:
                index = st.selectbox("문서 선택", range(len(docs)), format_func=lambda i: docs[i]["title"])
                doc = docs[index]
                st.caption(f"{doc['document_id']} · {doc['revision']} · {doc['status']}")
                with st.expander("문서 내용", expanded=True):
                    st.markdown(doc["body"])
                    st.caption(f"담당 {doc['owner']} · 적용일 {doc['effective_date']} · 연결 {doc['linked_ids']}")
            else:
                st.info("검색 결과가 없습니다. 다른 단어로 검색해 주세요.")
            if hasattr(repository, "save_embedding"):
                with st.expander("의미 검색"):
                    st.caption("버튼을 누르면 문서 또는 검색어가 API로 전송됩니다. 키 없이도 위의 단어 검색을 사용할 수 있습니다.")
                    if st.button("로컬 문서 벡터 생성", disabled=client is None):
                        try:
                            for doc in repository.browse_table("knowledge_documents", 100)["rows"]:
                                vector = client.embeddings.create(model=EMBEDDING_MODEL, input=doc["body"], dimensions=EMBEDDING_DIMENSIONS).data[0].embedding
                                repository.save_embedding(doc["document_id"], vector)
                            st.success("벡터 저장 완료")
                        except Exception:
                            st.error("벡터 생성 실패. 키와 DB 연결을 확인하세요.")
                    if st.button("가까운 문서 검색", disabled=not client or not query.strip()):
                        try:
                            vector = client.embeddings.create(model=EMBEDDING_MODEL, input=query, dimensions=EMBEDDING_DIMENSIONS).data[0].embedding
                            results = repository.nearest_knowledge(vector)
                            if not results:
                                st.info("저장된 벡터가 없습니다. 단어 검색 결과를 사용하세요.")
                            for result in results:
                                st.write(result["title"])
                                st.caption(result["text"])
                        except Exception:
                            st.error("의미 검색 실패. 단어 검색을 이용하세요.")
        elif panel == "공정 DB":
            tables = repository.list_tables()
            table = st.selectbox("테이블", [r["table"] for r in tables], format_func=lambda name: f"{name} ({next(r['rows'] for r in tables if r['table'] == name)}행)")
            page = st.number_input("페이지", min_value=1, value=1, step=1)
            result = repository.browse_table(table, 25, (page-1)*25)
            st.caption(f"전체 {result['total']}행 · 읽기 전용")
            if result["rows"]:
                st.dataframe(result["rows"], hide_index=True, width="stretch")
                record = st.selectbox("행 상세", range(len(result["rows"])), format_func=lambda i: str(next(iter(result["rows"][i].values()))))
                with st.expander("레코드 내용"):
                    st.json(result["rows"][record])
            else:
                st.info("이 페이지에 데이터가 없습니다.")
        elif panel == "확인 규칙":
            for rule in repository.get_rules():
                with st.expander(rule["name"]):
                    st.write(rule["condition"])
                    st.write(rule["action"])
                    st.caption(f"{rule['owner']} · {rule['source_document']} · {rule['revision']} · {rule['status']}")
        elif entity_ids:
            entity_id = st.selectbox(entity_label, entity_ids)
            snap = snapshot_builder(entity_id)
            st.write(snap["primary"])
            st.caption(snap["caption"])
            st.progress(max(0., min(1., snap["progress"]/100)), text=f"데모 진척 {snap['progress']:.0f}%")
            st.button(f"이 {entity_label} 브리핑", on_click=queue, args=(snap["brief"],), width="stretch")
            st.markdown("**담당자 확인 제안**")
            for item in snap["approvals"]:
                st.write("• " + item)
            st.caption("실제 승인 대기 기록이 아닌 데모 데이터 기반 확인 제안입니다.")
        else:
            st.info("등록된 배치가 없습니다.")

    with chat, st.container(key="chat_console"):
        st.markdown('<span id="agent-console"></span>', unsafe_allow_html=True)
        head, reset_col = st.columns([3, 1])
        head.subheader("니즈푸드 / Agent 대화")
        reset_col.button("새 대화", on_click=reset, width="stretch")
        st.caption("문서 · 공정 DB · 확인 규칙  /  데모 기준일 2026-09-03")
        with st.container(key="chat_history"):
            for i, msg in enumerate(st.session_state.messages):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg["role"] == "assistant" and "searched_documents" in msg:
                        if not msg["searched_documents"]:
                            st.caption("문서 검색이 실행되지 않은 답변입니다. 절차·기준은 문서로 추가 확인하세요.")
                        with st.expander("상세 근거"):
                            st.caption("조회: " + (", ".join(msg.get("data_tools", [])) or "없음"))
                            for evidence in msg.get("evidence", []):
                                st.write(evidence["filename"])
                                st.caption(evidence.get("text", "검색 본문 없음"))
                            st.caption("인용: " + (", ".join(msg.get("sources", [])) or "없음"))
                    if msg["role"] == "assistant":
                        with st.container(key=f"voice_play_{i}"):
                            if st.button("음성으로 듣기", key=f"speak_{i}", disabled=voice is None):
                                digest = hashlib.sha256(msg["content"].encode()).hexdigest()
                                try:
                                    if digest not in st.session_state.speech_cache:
                                        st.session_state.speech_cache[digest] = voice.speak(msg["content"])
                                    st.audio(st.session_state.speech_cache[digest], format="audio/mp3")
                                except Exception:
                                    st.error("음성 재생 실패. 텍스트 답변을 확인하세요.")
        if not agent:
            st.info("자연어 대화는 설정에서 API 키를 연결하세요. 문서·DB·규칙은 바로 조회할 수 있습니다.")
        typed = st.chat_input(chat_placeholder, disabled=agent is None, key="typed_question")
        if typed:
            queue(typed)
        with st.container(key="voice_panel"):
            with st.expander("음성 질문"):
                st.caption("녹음은 메모리에서 처리되며 전사 버튼을 누르면 설정된 API로 전송됩니다. 답변 음성은 AI가 생성합니다.")
                recording = st.audio_input("한국어 질문 녹음", key="voice_recording", disabled=voice is None)
                if st.button("녹음 전사", disabled=not voice or recording is None):
                    try:
                        data = recording.getvalue()
                        digest = hashlib.sha256(data).hexdigest()
                        if digest != st.session_state.voice_digest:
                            st.session_state.voice_draft = voice.transcribe(data)
                            st.session_state.voice_digest = digest
                    except Exception:
                        st.error("전사 실패. 20MB 이하로 다시 녹음하거나 직접 입력하세요.")
                transcript = st.text_area("전사 내용 확인·수정", key="voice_draft")
                st.button("음성 질문 보내기", disabled=not agent or not transcript.strip(), on_click=queue, args=(transcript.strip(),))

    question = st.session_state.pending_question
    if question:
        st.session_state.pending_question = None
        if not agent:
            st.info(f"선택한 질문: {question} — API 키를 연결한 후 다시 보내세요.")
        else:
            st.session_state.messages.append({"role": "user", "content": question, "created_at": timestamp()})
            try:
                with st.spinner("데이터와 문서 근거를 확인하고 있습니다…"):
                    answer = agent.ask(question, vector_store_id=st.session_state.vector_store_id,
                                       previous_response_id=st.session_state.previous_response_id, max_results=settings["max_results"])
                st.session_state.messages.append({"role": "assistant", "content": answer.text, "sources": answer.sources,
                    "evidence": answer.evidence, "data_tools": answer.data_tools, "searched_documents": answer.searched_documents, "created_at": timestamp()})
                st.session_state.previous_response_id = answer.response_id
            except Exception:
                st.session_state.previous_response_id = None
                st.session_state.messages.append({"role": "assistant", "content": "답변을 생성하지 못했습니다. 키 권한·모델 이름·네트워크를 확인한 후 다시 질문하세요.", "created_at": timestamp()})
            st.rerun()

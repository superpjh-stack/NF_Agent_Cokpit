# 니즈푸드 제조 AI Agent Cockpit

급식 생산과 임진감김치 제조 준비를 지원하는 Streamlit 업무 화면입니다. 문서·공정 DB·확인 규칙을 한 대화에서 조회하고, 담당자가 확인할 조치와 근거를 제시합니다.

**현재 데이터는 2026-09-03 기준 급식 데모이며 실제 운영 데이터가 아닙니다. 임진감김치의 승인 배합표·제조조건은 미등록입니다.** 김치 배합비나 공정 수치를 임의 생성하지 않습니다.

## 실행

Python 3.11 권장:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

API 키 없이 KPI·문서·테이블·규칙을 조회할 수 있습니다. 대화·음성·문서 API 인덱싱은 `OPENAI_API_KEY`가 필요합니다. `DATABASE_URL`이 비어 있으면 SQLite 오프라인 데모, 설정하면 PostgreSQL + pgvector를 사용합니다. DB 연결 실패를 SQLite로 숨기지 않습니다.

## 화면과 데이터

- 중앙: 근거형 대화, 새 대화, 문서 검색 여부, 상세 근거, 음성 질문·재생.
- 왼쪽: 지식문서·공정 DB·확인 규칙별 10개 질문과 대화 이력. 모두 직접 입력과 같은 `pending_question` 경로를 사용합니다.
- 오른쪽: 문서 검색·본문·개정/담당자/적용일, 테이블별 행 수·페이지·행 상세, 규칙과 배치 확인사항.
- 모바일: 대화와 입력을 중심으로 보조 패널을 숨깁니다.

기존 메뉴·배치·조리값·검식·원료재고·식당 원가·출하·설비 이벤트 모델을 유지합니다. `knowledge_documents`, `rules`, `settings`를 추가했습니다. `sample_docs/knowledge`의 문서 10개와 규칙 7개는 모두 **데모·미승인**이며 최초 초기화 시 DB에 저장됩니다. 같은 ID의 문서를 재시작 때 덮어쓰지 않습니다.

문서 검색은 API 키 없이 한국어 단어/문자 조각으로 동작합니다. PostgreSQL의 의미 검색 패널에서 명시적으로 벡터를 생성하면 `vector(1536)`과 HNSW 인덱스로 검색합니다. 임베딩이 없으면 단어 검색을 사용합니다. 현재 자료는 하나의 데모 데이터셋으로 취급하며, 실제 데이터를 연결할 때 도구의 `demo_data` 표시와 문서 승인 상태도 함께 수정해야 합니다.

임진감김치 제조에는 제품 유형, 승인 배합표 버전, 목표 생산량의 중량 기준, 공정별 수율과 품질기준이 필요합니다. 기존 `qty_per_meal`은 1식 기준이며 김치 kg 배합이 아닙니다. 현재 재고에는 원료 LOT·예약량·품질보류량이 없어 실제 사용가능량이나 전체 LOT 계보를 확정할 수 없습니다.

임진감김치 전용 데이터 구조와 읽기 전용 도구는 준비되어 있습니다. `kimchi_products`, `kimchi_formulations`, `kimchi_formulation_items`, `kimchi_material_lots`, `kimchi_production_lots`, `kimchi_lot_inputs`, `kimchi_process_records`, `kimchi_packaging_lots`, `kimchi_quality_results`는 실제 승인 자료와 생산기록을 적재하기 전까지 비어 있습니다. 급식 데모 값으로 자동 채우지 않습니다.

최신 V2는 [v2/README.md](v2/README.md)의 React·TypeScript + FastAPI 앱으로 별도 실행합니다. V1 Streamlit과 DB를 공유하지 않으며, V2 데모 조회는 무키로 동작하고 AI·음성은 서버 설정과 접근 코드가 필요합니다.

최신 임진강김치 Agent Cockpit의 V1 업무 모델도 반영했습니다. `kimchi_lots` 계보, `kimchi_process_measurements` 절임·발효 측정, `kimchi_ccp_checks`, `kimchi_fermentation_predictions`, `kimchi_inventory`, `kimchi_shipments`, `kimchi_claims`를 별도 네임스페이스로 관리합니다. 이 데이터는 최신 참고 프로젝트의 **가상 데모**이며 실제 운영·HACCP 승인값이 아닙니다.

- `get_lot_trace`: 원재료 입고부터 포장까지 부모·자식 LOT 계보
- `get_fermentation_status`, `get_process_measurements`: 염도·pH·온도·산도·중량·설비상태와 시제품 예측
- `get_ccp_deviations`: CCP 주의·부적합 이력
- `get_shipment_readiness`: 출하 승인상태와 계보 전체의 CCP·발효 근거
- `get_claim_trace`: 클레임에서 출하·포장·발효·절임·원재료 역추적

- `get_kimchi_readiness`: 제품 유형·승인 배합·중량 기준·근거 문서와 원료 목록의 등록 여부를 확인합니다.
- `calculate_kimchi_materials`: 승인 상태인 kg 배합만 같은 중량 기준으로 환산하며, 원료별 0.001kg 반올림과 합계 차이를 반환합니다. 확인된 LOT 재고에서 예약량과 품질보류량을 빼고 부족량을 계산하며 재고가 없으면 `미확인`으로 둡니다.
- `get_kimchi_lot_trace`: 원료 LOT, 공정 실측, 포장 LOT, 품질 결과의 누락 여부를 보수적으로 판정합니다.

수율은 승인 배합 또는 공정 실측값이 별도 등록되기 전에는 적용하지 않습니다. 현재 산출물 상태는 `제조 검토용 초안`이며, 실제 사용 전 승인 배합표의 문서명·개정번호·적용일과 제품 유형을 등록해야 합니다.

## API 설정과 근거

서버 기본 키는 프로젝트 `.env` 또는 컨테이너 환경에서 매 세션 적용합니다. 전체 키를 입력창에 미리 넣지 않으며 끝 4자리와 출처만 보여줍니다. 접힌 설정 폼의 빈 키는 현재 값을 유지하고, 입력한 키는 세션에만 적용합니다. 키가 바뀌면 Responses 대화 연결 및 업로드 연결을 초기화합니다. 서버 기본값 복귀 버튼을 제공합니다. 서버 문서 저장소 ID만 DB 설정으로 유지하며 키는 저장하지 않습니다.

기본 모델의 단일 출처는 `needs_agent/config.py`입니다. `.env.example`과 Compose의 `OPENAI_MODEL`은 빈칸으로 이 기본값을 사용하며, 별도 값으로 재정의할 수 있습니다. 호출당 35초 제한·1회 재시도를 적용합니다.

읽기 전용 도구 허용 목록, strict 스키마, 함수 호출 4라운드 상한을 사용합니다. 상한에서는 `tool_choice: none`으로 마무리하고, 중간 라운드의 검색 근거도 누적합니다. 절차·배합·승인·검사·규칙 질문은 로컬 문서를 먼저 검색합니다. 답변은 최대 5줄과 마지막 `근거:` 줄을 지시하며 상세 근거는 펼침 영역에 표시합니다.

음성은 메모리에서 처리하며 전사 버튼으로 API에 전송합니다. 녹음 20MB, 음성 재생 텍스트 3000자 제한이 있습니다. 전사 내용을 수정하고 별도 전송 버튼으로 질문합니다. 새 대화에서도 녹음 위젯 키를 유지합니다.

구현 참고: [OpenAI 함수 호출](https://developers.openai.com/api/docs/guides/function-calling), [Streamlit 컨테이너](https://docs.streamlit.io/develop/api-reference/layout/st.container), [Streamlit 음성 입력](https://docs.streamlit.io/develop/api-reference/widgets/st.audio_input).

## PostgreSQL 이관

운영 백엔드는 PostgreSQL + pgvector입니다. SQLite는 오프라인 시제품/테스트용입니다. 새 DB에서 어댑터를 등록하기 전에 `vector` 확장을 생성·커밋합니다.

기존 SQLite를 최신 앱으로 한 번 열어 문서·규칙·설정 테이블을 초기화한 뒤, 대상 DB를 백업하고 이관합니다:

```bash
export DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/DB'
python scripts/migrate_sqlite_to_postgres.py data/needs_food_demo.db --replace
```

`--replace`는 대상의 업무·문서·규칙·설정 데이터를 **전체 교체**합니다. 하나의 트랜잭션으로 옮기고 행 수를 검증하며, 반복 실행해도 중복되지 않습니다. 소스는 읽기 전용으로 열립니다. 문서 벡터는 이관 후 다시 생성합니다. 도구 대화에서 이관을 자동 실행하지 않습니다.

## Docker Compose 배포

Docker와 Compose가 설치된 호스트의 `.env`에 다음을 설정합니다:

```dotenv
POSTGRES_PASSWORD=강력한비밀번호
DATABASE_URL=postgresql://needs_food:URL_ENCODED_PASSWORD@postgres:5432/needs_food
OPENAI_API_KEY=
OPENAI_MODEL=
```

`DATABASE_URL` 비밀번호에는 `POSTGRES_PASSWORD`와 같은 값을 URL 인코딩해 사용합니다. 컨테이너 간 호스트 이름은 `postgres`입니다. 비밀번호와 DB URL이 없으면 Compose는 시작하지 않습니다.

```bash
docker compose config --quiet
docker compose up --build -d
docker compose logs --tail=100 app postgres
```

앱은 PostgreSQL 상태 확인 후 시작합니다. DB는 이름 있는 볼륨에 유지되며, 앱은 8501 포트에 노출됩니다. 외부 서비스 배포에는 호스트의 접근 제어와 HTTPS 구성을 적용하세요. 이 시제품에는 사용자 인증 기능이 없습니다.

키 교체는 대상 호스트 `.env` 또는 Hostinger Docker Manager 환경값의 `OPENAI_API_KEY`를 수정한 후 `docker compose up -d --force-recreate app`으로 반영합니다. `.env`는 커밋하거나 이미지에 포함하지 않습니다. Docker 이미지는 실행 파일·샘플 문서·데모 SQLite만 복사합니다.

## 검증

```bash
python -m pytest -q
TEST_POSTGRES_ADMIN_URL='postgresql://USER:PASSWORD@localhost:PORT/postgres' python -m pytest tests/test_postgres.py -q
```

PostgreSQL 테스트는 임시 DB를 만들고 제거하므로 테스트 전용 관리자 URL을 사용합니다. URL이 없으면 해당 테스트만 건너뜁니다. 새 DB의 확장·HNSW 인덱스·벡터 검색·설정 유지·두 번의 전체 이관을 검증합니다. Streamlit 테스트는 화면 렌더링·새 대화 반복·그룹/테이블 전환·키 변경과 복귀를 다룹니다.

브라우저 검증은 앱 실행 후 개발 의존성 `playwright`를 설치하고 `python scripts/browser_smoke.py`로 실행합니다. 기본적으로 macOS Chrome을 사용하며, 다른 환경에서는 `CHROME_EXECUTABLE`로 실행 경로를 지정합니다. 캡처와 결과는 `artifacts/`에 저장됩니다.

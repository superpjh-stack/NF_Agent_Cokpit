# 니즈푸드 제조 AI Agent V2

React 19·TypeScript·Vite와 FastAPI로 구성한 급식 제조 업무 도우미입니다. 기존 Streamlit V1은 루트에서 별도로 실행합니다. 현재 V2는 SQLite를 사용하며 기본 DB는 `data/needs_food_v2_demo.db`입니다.

## 현재 화면과 기능

- PC: 질문 이력·추천질문, 중앙 대화·생산 배치 선택, 지식베이스·DB 패널.
- 모바일: 자료·질문 버튼으로 보조 패널을 열고 닫습니다.
- 생산·품질 / 문서·규칙 추천질문 각 10개와 직접 입력·이력 재질문을 같은 경로로 처리합니다. 최근 질문 최대 20개는 sessionStorage에 저장합니다.
- 지식문서 검색·본문 확인, 허용 테이블의 첫 10개 레코드 조회를 제공합니다.
- 답변에 문서와 원본 조회 기록을 연결하고, 답변 복사·대화 초기화·LOT 변경 시 이전 요청 취소를 지원합니다.
- 데모 모드는 정해진 DB·문서 조회입니다. AI 모드는 서버 키로 호출하며 샘플 근거가 포함되면 별도로 표시합니다.
- 실시간 음성은 WebRTC 연결·자막·음소거·종료를 제공합니다. 유효한 서버 자격증명과 HTTPS 또는 localhost가 필요합니다.

급식 샘플 기준일은 **2026-09-03**이며 지식문서·규칙은 **미승인 예시**입니다. 조리 측정의 호환 API 이름이 `fermentation_status`여도 발효 예측이 아닙니다. 오늘 입고 이력과 실시간 출하 기록은 연결되어 있지 않습니다.

## “니즈” 호출명 응답

매 질문을 **니즈 / 니즈야 / 니즈님**으로 시작해야 답변합니다. 예: “니즈, 오늘 재고 알려줘”. 이름 뒤에는 공백·구두점·문장 끝이 필요하며 “니즈푸드”, “비즈니스 니즈”는 호출로 보지 않습니다. 이전 질문에서 호출했어도 다음 질문에는 다시 불러야 합니다.

문자 입력은 브라우저와 서버가 모두 검사합니다. 호출명 없는 API 질문은 조회·AI 호출 없이 빈 답변과 `ignored: true`를 반환합니다. 추천질문과 DB 기록 질문에는 호출명을 명시하며 과거 이력이나 직접 입력에 몰래 붙이지 않습니다. 정책의 원본은 `v2/wake.py`이며 workspace 메타데이터로 브라우저에 전달합니다.

음성은 자동 응답·자동 끼어들기를 끄고 최종 전사에서 호출을 확인한 뒤 답변합니다. 원본 오디오 항목은 대화에서 삭제하고, 호출된 질문과 그 답변만 별도 입력으로 전달합니다. 중복 전사는 무시하며 응답·도구 조회·음성 재생이 끝난 뒤 다음 호출된 질문을 처리합니다. LOT 변경·종료 시 대기 질문·요청·마이크 자원을 정리합니다.

마이크가 연결된 동안 음성은 호출명 판정을 위해 전사 서비스에 전송됩니다. 로컬 호출어 감지가 아니며 인식 오류로 호출을 놓칠 수 있습니다. 실제 마이크·유료 음성 검증은 별도입니다. 구현 계약: [OpenAI Realtime 수동 응답](https://developers.openai.com/api/docs/guides/realtime-conversations), [명시적 응답 입력](https://developers.openai.com/api/reference/resources/realtime/client-events).

## 수량과 근거 계약

생산 배치에는 `quantity`와 `unit: "식"`을 반환합니다. 기존 필드 `quantity_kg`는 실제 kg 값이 아니므로 null입니다. 출하 계획·실적 역시 식 단위입니다. 재고에는 DB 원본의 `quantity`, `safety_stock`, `unit`을 보존하며 `quantity_kg`·`safety_stock_kg`는 원본 단위가 kg일 때만 값이 있습니다. 숫자를 kg로 임의 변환하지 않습니다.

급식으로 재매핑된 V2 도구는 `demo_data: true`, 급식 샘플 출처, 기준일과 UTC 조회시각을 반환합니다. AI 생성 여부(`mode`)와 샘플 사용 여부(`demo_data`)는 별개입니다. 승인 배합·원료 LOT 자료가 필요한 임진감김치 전용 도구를 급식 배합으로 대체하지 않습니다.

## 로컬 실행

프로젝트 루트에서 Python 3.12와 Node 22를 사용합니다.

```bash
python3.12 -m venv .venv-v2
.venv-v2/bin/pip install -r v2/requirements.lock
npm ci --prefix v2/web
npm run build --prefix v2/web
.venv-v2/bin/uvicorn v2.api:app --host 127.0.0.1 --port 8510
```

접속 주소는 `http://127.0.0.1:8510`입니다. 화면 개발은 `npm run dev --prefix v2/web`로 실행하며 Vite가 `/api`를 8510으로 프록시합니다. 루트 `.env`를 읽고 환경변수가 우선합니다. SQLite 경로는 `V2_SQLITE_PATH`로 바꿉니다. 현재 `DATABASE_URL`로 V2 PostgreSQL 어댑터가 연결되지는 않습니다.

로컬 조회는 API 키 없이 동작합니다. 현재 화면에는 로그인 UI가 없으므로 로컬 데모는 `V2_REQUIRE_LOGIN` 미설정 또는 `0`을 사용합니다.

## AI·음성 연결

서버에 `OPENAI_API_KEY`를 설정합니다. 외부 유료 호출 보호에는 `COCKPIT_ACCESS_TOKEN`을 설정하고 화면의 **AI 연결 설정**에서 접근 코드를 입력합니다. 서버가 호스트·클라이언트 주소를 확인한 로컬 개발 접속은 코드 없이 AI를 사용할 수 있습니다. 설정 변수는 `v2/.env.example`과 `v2/api.py`를 참고하세요.

API 키는 서버에만 둡니다. 접근 코드는 sessionStorage에 보관되어 같은 탭 새로고침 후에도 유지됩니다. 사용자 계정·조직 권한과는 별도입니다. 외부 운영 인증을 해제해 로그인 UI 누락을 우회하지 않습니다.

문자 모델은 `needs_agent/config.py`의 기본값 또는 `OPENAI_MODEL`을 사용합니다. 실시간 모델·음성은 `OPENAI_REALTIME_MODEL`, `OPENAI_REALTIME_VOICE`로 설정합니다. 앱은 실시간 마이크 녹음 파일을 저장하지 않으며 자막은 세션에서 표시합니다.

## 남은 연결 작업

- 업무 계정·저장·인계 API와 WorkBoard/PilotMetrics 컴포넌트는 존재하지만 현재 App은 렌더링하지 않습니다. `/work/{id}`도 업무 이어보기 UI가 완성된 상태가 아닙니다.
- 실시간 센서 API 경로는 있으나 센서 도구 스키마·핸들러·외부 데이터 어댑터가 연결되어 있지 않습니다.
- PostgreSQL 클래스는 V2에서 실제 연결을 구현하지 않습니다. 공용 PostgreSQL 코드와 V2 연결 여부를 구분해야 합니다.
- 전체 원료 LOT 계보, 사용가능 재고, 운영 승인 기준은 별도 원본 자료·현장 연동이 필요합니다.

[v2.0 제품 기획](../docs/v2.0-product-plan.md)과 [개발 명세](../docs/v2.0-delivery-spec.md)는 계획 문서이며 현재 제공 기능 목록이 아닙니다.

## Docker 구성 상태

`v2/Dockerfile`은 프런트 빌드 후 Python 일반 사용자로 실행합니다. Compose 이미지 이름은 `needs-food-cockpit-v2:local`, 기본 포트는 `8503:8510`입니다. 그러나 현재 Compose의 PostgreSQL은 V2에서 사용되지 않으며 SQLite 영속 볼륨도 없습니다. 기본 `V2_REQUIRE_LOGIN=1`에 필요한 로그인 UI 역시 미연결입니다.

운영 배포 전에 DB 영속성·실제 어댑터·로그인 UI를 연결하고 검증해야 합니다. 현재 Compose를 배포 완료 구성으로 간주하지 않습니다.

## 검증

```bash
npm run build --prefix v2/web
node --test v2/tests/wake-voice.cjs
.venv-v2/bin/python -m pytest v2/tests/test_wake.py -q
.venv-v2/bin/python -m pytest v2/tests/test_provenance_units.py v2/tests/test_ai_connection.py -q
.venv-v2/bin/python -m pytest v2/tests -q
```

전체 테스트에는 현재 급식 V2와 맞지 않는 기존 김치·업무 테스트가 포함되어 있습니다. 실패를 이번 변경의 회귀와 구분해서 확인합니다. DB 테스트는 임시 DB를 사용합니다. UI는 PC와 390px에서 질문·근거·LOT 변경·자료 패널을 확인합니다. 실제 유료 AI·음성, PostgreSQL, Docker와 휴대전화 마이크는 별도 검증 대상입니다.

2026-10-09 검증: 프런트 빌드 성공, 출처·단위 및 AI 연결 테스트 19개 통과. 전체 V2 테스트는 변경 전 14개 통과·15개 실패, 변경 후 27개 통과·15개 실패로 실패 항목은 동일했습니다. PC·390px 브라우저에서 직접/추천 질문, 원본 근거 단위, LOT 변경, 대화 초기화와 자료 패널을 확인했습니다. 실제 유료 AI·음성, PostgreSQL, Docker, 실기기 마이크 검증은 실행하지 않았습니다.

2026-10-10 호출명 검증: 관련 Python 테스트 37개, 음성 이벤트 모의 테스트 6개, 프런트 빌드 통과. 전체 V2 테스트 45개 통과·기존 실패 15개로 새 실패 항목은 없습니다. PC·390px 화면에서 미호출 입력 차단·호출된 추천질문 응답·초기화를 확인했습니다. 실제 마이크·유료 음성은 실행하지 않았습니다.

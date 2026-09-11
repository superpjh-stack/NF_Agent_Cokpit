# 기존 니즈푸드 프로젝트 연결

원본 프로젝트 위치: `/Users/gerardo92/Desktop/AI Coding/08 AI Agent Making Agent/needs-food-ai-agent`.
다른 환경에서는 현재 작업 폴더의 `README.md`와 아래 파일로 프로젝트를 확인한다.

## 확인할 구현

- `needs_agent/prompts.py`: 기존 현장 이해·요약·경고 원칙 및 승인 경계.
- `needs_agent/factory_tools.py`: 실제 도구 이름과 인자 정의.
- `needs_agent/data_hub.py`: SQLite 스키마와 데모 데이터.
- `needs_agent/service.py`: 정형 데이터 도구와 문서 검색 연결.
- `sample_docs/`: 가상 단체급식 자료. 임진감김치 제품 기준으로 전용하지 않는다.

## 조회 기능과 한계

아래는 기존 앱 내부 함수 도구이며 Codex에 자동 연결되어 있는 도구가 아니다. 연결된 실행 환경 또는 실제 구현을 확인한 뒤 사용한다.

| 도구 | 용도 | 주의 |
|---|---|---|
| get_inventory_status | 원료명별 재고·안전재고 조회 | 현재 스키마에는 원료 LOT·예약·보류량이 없어 사용가능량 확정 불가 |
| get_batch_trace | 정확한 배치 ID의 실적·검사 추적 | 솥 기반 데모이며 김치 공정 LOT 계보가 아님 |
| get_quality_summary | 날짜·메뉴별 내부/외부 검사 조회 | 조회 제품과 표본 범위를 확인 |
| get_recipe_cost | 메뉴별 식당 사용량·원가 | qty_per_meal은 1식 기준이며 김치 kg 배합으로 해석 불가 |
| get_daily_briefing / get_production_delays | 생산·출하 현황 및 지연 | 날짜를 명시한다. null은 데모 날짜를 조회할 수 있음 |
| get_cooking_conditions | 솥 온도·교반·압력 조회 | 김치의 절임·발효 조건으로 대체 불가 |

## 앱 확장을 요청받은 경우

기존 데이터를 보존하고 임진감김치의 제품 코드, 배합 버전, kg 기준 BOM, 원료·제조·포장 LOT 연결, 공정 실측 및 품질기준을 실제 제공 자료에 맞춰 추가한다. 없는 레코드는 합성 운영 데이터로 채우지 않는다. 예시가 필요하면 데모로 명확히 분리한다.

읽기 전용 조회·계산부터 연결하고 기준·실측·문서 근거를 함께 답하도록 한다. 배합 환산, 단위 불일치, 재고 미확인, 기준 미등록 시 판정 보류를 검증한다. 스킬 설치만으로 앱의 시스템 프롬프트나 데이터베이스가 변경되지는 않는다.

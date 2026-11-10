# 니즈푸드 V2 AWS 배포

기존 서비스와 분리된 ECS/Fargate + ALB + CloudFront HTTPS 검증 배포다.

- 스택: `NeedsFoodV2Web`
- ECR: `needsfood-v2-web`
- ECS: `needsfood-v2-web`
- SQLite 데모 데이터를 사용하며 운영 PostgreSQL은 연결하지 않는다.
- 현재 V2 화면에 업무 계정 로그인 UI가 없으므로 `V2_REQUIRE_LOGIN=0`으로 기록 조회를 허용한다.
- OpenAI 호출은 Secrets Manager의 `COCKPIT_ACCESS_TOKEN`으로 보호한다.

실제 마이크·OpenAI Realtime 연결은 브라우저에서 HTTPS URL로 별도 확인한다.

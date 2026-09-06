# blog-generator

공식문서를 근거로 한국어 학습 노트를 자동 생성해 `_posts/ai-notes/`에 발행하는 파이프라인.

## 설계 원칙
- **공식문서-only**: 주제는 실제 공식문서 URL에 1:1로 묶이고, 생성기는 **fetch한 내용만 근거**로 글을 쓴다(환각·표절 차단).
- **저작권 안전**: 복붙/통째번역 금지, 출처 1:1 표기, 1인칭 가짜경험 금지 — 시스템 프롬프트(`prompts/`)에 규칙으로 강제. 소스도 허용적 라이선스만 사용(Apache/PostgreSQL/RFC/man). CC-NC 등 회색지대(Redis·Spring)는 제외.
- **robots 준수**: fetch 전 `robots.txt`를 자동 확인하고 차단 시 스킵.
- **품질 게이트**: 얕은 출처와 잘못된 출력 구조를 먼저 차단하고, 생성 후에는 독립 모델이 근거·구성·가독성을 검수한다.
- **투명성**: 상단 "AI 생성" 배지 + 하단에 생성 모델명·출처 자동 기재.
- **중복 방지**: 이미 쓴 주제(`state/topics_done.json`)와 겹치면 건너뛴다. 미생성 주제가 없으면 생성하지 않는다.

## 구조
```
generator/
  main.py               # CLI 조립 지점(설정 + 현재 구현체 연결)
  pipeline.py           # 생성 유스케이스 실행 순서
  contracts.py          # Article 데이터와 Protocol 교체 계약
  quality.py            # 출처·본문·검수 JSON의 순수 검증 규칙
  review_pipeline.py    # 독립 검수 → 수정 → 재검수
  source_context.py     # 공식문서를 XML 프롬프트 컨텍스트로 변환
  topics.py             # 분야 균형·난이도 기반 주제 선택 정책
  llm.py                # OpenRouter 모델 어댑터와 fallback
  publishing.py         # Jekyll Publisher 어댑터
  sources.json          # 프롬프트/모델/catalogs/topics/품질 설정
  prompts/
    system.md           #   시스템 프롬프트(지시는 영어, 출력은 한국어)
    user_template.md
    reviewer.md         #   독립 검수 기준
    review_template.md
    revision_template.md
  catalog.py            # 주제 자동 발굴(GitHub 트리 / man 인덱스 / RFC 인덱스)
  fetcher.py            # robots 체크 + fetch + 본문 추출
  dedup.py              # 중복 방지
  post_writer.py        # 마크다운 교정 + D2→SVG 렌더 + frontmatter/배지/출처 → .md
  state/topics_done.json
```

`pipeline.py`는 구체적인 OpenRouter·Jekyll·웹 수집 모듈을 직접 알지 않고
`LanguageModelGateway`, `Publisher`, `TopicRepository`, `SourceGateway` Protocol에
의존한다. 다른 모델 제공자, HTML 출력, 주제 저장소, 문서 수집 방식을 추가할 때
같은 계약을 구현해 `main.py`의 조립 코드만 바꾸면 된다.

## 로컬 실행
```bash
cd generator
pip install -r requirements.txt
cp .env.example .env          # .env 에 OPENROUTER_API_KEY 입력 (커밋 안 됨)
python main.py                # 다음 미생성 주제 1편 생성
FORCE_TOPIC_ID=cs-websocket-protocol python main.py   # 특정 주제 강제
```
> 다이어그램(D2) 렌더링에 `d2` 필요: `brew install d2`

## 자동 실행 (GitHub Actions)
- `.github/workflows/generate-post.yml` 가 **매일 KST 06:00**(UTC 21:00)에 실행.
- repo Settings → Secrets and variables → Actions 에 **`OPENROUTER_API_KEY`** 등록 필요.
- 수동 실행: Actions 탭 → "Generate daily study post" → Run workflow(주제 id 입력 가능).
- 같은 repo라 별도 토큰 불필요(내장 `GITHUB_TOKEN`으로 커밋).

## 주제 추가
- **자동(권장)**: `sources.json`의 `catalogs`에 소스(레포/인덱스 + 필터)를 추가하면 페이지들이 자동으로 주제가 된다.
- **수동 보충**: 카탈로그로 안 잡히는 건 `topics` 배열에 항목을 추가(실제 공식문서 URL 필수).
- 새 소스는 반드시 **라이선스·robots를 먼저 확인**할 것(README 상단 원칙 참고).

## 무료모델
`model_selection: auto`면 실행 시 OpenRouter에서 현재 무료모델을 실시간 조회해 fallback 체인을 자동 구성한다(목록이 바뀌어도 자동 대응). 선호·제외는 `model_prefer` / `model_exclude`로 조정.

## 프롬프트
`prompts/system.md`가 글쓰기 규칙(근거 제한·톤·가독성·D2 다이어그램·출력 계약)을 XML 태그로 구분한다. `prompts/user_template.md`는 공식문서 원문을 `<document>` 단위로 격리하며, 긴 원문을 먼저 배치하고 작성 요청을 마지막에 둔다. 지시문은 영어지만 **출력은 한국어**로 강제한다.

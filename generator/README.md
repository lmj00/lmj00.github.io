# blog-generator

공식문서를 근거로 한국어 학습 노트를 자동 생성해 `_posts/ai-notes/`에 발행하는 파이프라인.

## 설계 원칙
- **공식문서-only**: 주제는 실제 공식문서 URL에 1:1로 묶이고, 생성기는 **fetch한 내용만 근거**로 글을 쓴다(환각·표절 차단).
- **저작권 안전**: 복붙/통째번역 금지, 출처 1:1 표기, 1인칭 가짜경험 금지 — 시스템 프롬프트(`prompts/`)에 규칙으로 강제. 소스도 허용적 라이선스만 사용(Apache/PostgreSQL/RFC/man). CC-NC 등 회색지대(Redis·Spring)는 제외.
- **robots 준수**: fetch 전 `robots.txt`를 자동 확인하고 차단 시 스킵.
- **품질 게이트**: 생성 결과에 일본어/한자가 섞이면 버리고 다음 모델로 재시도.
- **투명성**: 상단 "AI 생성" 배지 + 하단에 생성 모델명·출처 자동 기재.
- **중복 방지**: 이미 쓴 주제(`state/topics_done.json`)와 겹치면 건너뛴다. 미생성 주제가 없으면 생성하지 않는다.

## 구조
```
generator/
  sources.json          # 설정 전체: 프롬프트/모델/catalogs/topics/필터
  prompts/
    system.md           #   시스템 프롬프트(지시는 영어, 출력은 한국어)
    user_template.md
  catalog.py            # 주제 자동 발굴(GitHub 트리 / man 인덱스 / RFC 인덱스)
  fetcher.py            # robots 체크 + fetch + 본문 추출
  llm.py                # OpenRouter 무료모델 실시간 조회 + fallback + 품질 게이트
  dedup.py              # 중복 방지
  post_writer.py        # 마크다운 교정 + D2→SVG 렌더 + frontmatter/배지/출처 → .md
  main.py               # 오케스트레이터
  state/topics_done.json
```

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
`prompts/system.md`가 글쓰기 규칙(저작권·톤·가독성·D2 다이어그램). 지시문은 영어지만 **출력은 한국어**로 강제한다.

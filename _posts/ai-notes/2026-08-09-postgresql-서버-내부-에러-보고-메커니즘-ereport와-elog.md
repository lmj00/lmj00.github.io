---
title: "PostgreSQL 서버 내부 에러 보고 메커니즘: ereport와 elog"
layout: post
categories: ai-notes
type: study-note
date: 2026-08-09 06:33:37 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-08-09
sources:
  - https://www.postgresql.org/docs/current/error-message-reporting.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: PostgreSQL 서버 코드 내에서 에러, 경고, 로그 메시지를 생성할 때는 `ereport` 매크로 또는 `elog` 함수를 사용하며, 심각도 수준과 메시지 텍스트를 필수로 지정하고 SQLSTATE 코드, 힌트, 상세 정보 등 다양한 보조 요소를 추가할 수 있다.

### 개요
PostgreSQL 서버 코드 내에서 발생하는 에러, 경고, 로그 메시지는 통일된 방식으로 생성되어야 한다. 이를 위해 제공되는 핵심 메커니즘이 `ereport` 매크로와 그 이전 버전인 `elog` 함수다. 이 도구들을 사용하면 메시지의 심각도, 내용, 그리고 애플리케이션이 자동으로 처리할 수 있는 구조화된 메타데이터를 일관되게 정의할 수 있다. 이는 사용자에게 명확한 피드백을 제공하고, 로그 분석 및 국제화(i18n)를 지원하는 데 필수적이다.

### ereport의 기본 구조
`ereport`는 C 소스 코드에서 단일 함수 호출처럼 보이도록 설계된 매크로다. 모든 메시지는 두 가지 필수 요소를 가져야 한다: **심각도 수준**과 **기본 메시지 텍스트**다.

심각도 수준은 `src/include/utils/elog.h`에 정의되어 있으며, `DEBUG`부터 `PANIC`까지의 범위를 가진다. 기본 메시지 텍스트와 여러 선택적 요소들은 `ereport` 호출 내부에서 보조 함수들을 호출하여 지정한다.

다음은 0으로 나누기 에러를 보고하는 전형적인 `ereport` 호출 예시다.
```c
ereport(ERROR,
        errcode(ERRCODE_DIVISION_BY_ZERO),
        errmsg("division by zero"));
```
이 예에서 `ERROR`는 심각도, `errcode(ERRCODE_DIVISION_BY_ZERO)`는 SQLSTATE 에러 코드, `errmsg("division by zero")`는 기본 메시지를 지정한다. 보조 함수 호출은 어떤 순서로든 작성 가능하지만, 관례적으로 `errcode`와 `errmsg`가 먼저 온다.

심각도가 `ERROR` 이상이면, `ereport`는 현재 쿼리 실행을 중단하고 호출자에게 제어를 반환하지 않는다. `ERROR`보다 낮은 심각도에서는 정상적으로 반환한다.

### 보조 보고 루틴
`ereport`와 함께 사용할 수 있는 주요 보조 루틴들은 다음과 같은 역할을 한다.

| 루틴 | 용도 | 비고 |
| :--- | :--- | :--- |
| `errcode(sqlerrcode)` | SQLSTATE 에러 식별자 코드 지정 | 생략 시 심각도에 따라 기본값 적용(`ERROR` 이상: `ERRCODE_INTERNAL_ERROR`, `WARNING`: `ERRCODE_WARNING`, `NOTICE` 이하: `ERRCODE_SUCCESSFUL_COMPLETION`) |
| `errmsg(const char *msg, ...)` | 기본 에러 메시지 텍스트 지정 | `sprintf` 스타일 포맷 코드 사용 가능. `%m`은 현재 `errno`에 대한 `strerror` 메시지를 삽입. |
| `errmsg_internal(...)` | `errmsg`와 동일하지만, 번역되지 않음 | 번역 가치가 없는 "발생 불가" 경우에 사용. |
| `errmsg_plural(...)` | 복수형 지원 메시지 | |
| `errdetail(const char *msg, ...)` | 선택적 "상세" 메시지 제공 | 기본 메시지에 넣기 부적절한 추가 정보용. |
| `errdetail_log(...)` | `errdetail`과 동일하지만, 메시지가 **서버 로그에만** 기록됨 | 클라이언트에 보내기에는 보안상 민감하거나 너무 방대한 상세 정보용. |
| `errhint(const char *msg, ...)` | 선택적 "힌트" 메시지 제공 | 문제 해결 방법에 대한 제안용. |
| `errcontext(const char *msg, ...)` | 에러 발생 컨텍스트 정보 제공 | 주로 `error_context_stack` 콜백 함수에서 사용. |
| `errposition(int cursorpos)` | 쿼리 문자열 내 에러의 텍스트 위치 지정 | |
| `errtable(Relation rel)`<br>`errtablecol(...)`<br>`errtableconstraint(...)`<br>`errdatatype(Oid datatypeOid)`<br>`errdomainconstraint(...)` | 관련 데이터베이스 객체(테이블, 컬럼, 제약조건, 데이터 타입 등)의 이름을 에러 보고에 보조 필드로 포함 | **이 중 하나만** 한 `ereport` 호출에서 사용해야 함. 애플리케이션이 지역화된 메시지 텍스트를 파싱하지 않고도 객체 이름을 추출할 수 있게 함. |
| `errcode_for_file_access()` | 파일 접근 관련 시스템 호출 실패에 적합한 SQLSTATE 선택 | `%m`과 함께 사용하는 것이 일반적. |
| `errcode_for_socket_access()` | 소켓 관련 시스템 호출 실패에 적합한 SQLSTATE 선택 | |
| `errhidestmt(bool hide_stmt)` | postmaster 로그에서 `STATEMENT:` 부분 억제 지정 | |
| `errhidecontext(bool hide_ctx)` | postmaster 로그에서 `CONTEXT:` 부분 억제 지정 | |

### elog 함수
`elog`는 `ereport`의 이전 버전으로 여전히 널리 사용된다. `elog(level, "format string", ...);` 호출은 `ereport(level, errmsg_internal("format string", ...));`와 정확히 동일하다. **항상 SQLSTATE 에러 코드가 기본값으로 설정되며, 메시지 문자열은 번역 대상이 아니다.** 따라서 `elog`는 내부 에러나 저수준 디버그 로깅에만 사용해야 하며, 일반 사용자에게 의미 있는 메시지는 `ereport`를 통해 생성해야 한다. 그럼에도 불구하고 시스템 내부의 "발생 불가" 에러 검사에는 표기법이 간단한 `elog`가 선호된다.

### 고려사항 및 주의점
* `errtable`, `errtablecol` 등의 객체 관련 함수는 한 `ereport` 호출에서 **최대 하나만** 사용해야 한다.
* `errmsg`의 포맷 코드 `%m`을 사용할 때는 `strerror(errno)`를 매개변수 목록에 명시적으로 작성해서는 안 된다. `%m`은 자동으로 `ereport` 호출에 도달했을 때의 `errno` 값을 사용한다.
* `errdetail`과 `errdetail_log`을 모두 사용하면 하나는 클라이언트에, 다른 하나는 로그에 전송된다.
* `errcontext`는 다른 보조 함수와 달리 한 `ereport` 호출 내에서 여러 번 호출될 수 있으며, 제공된 문자열들은 줄바꿈으로 구분되어 연결된다.

### 정리
PostgreSQL 서버 내부의 모든 메시지 생성은 `ereport` 매크로를 표준으로 한다. 필수적인 심각도와 메시지에 더해, SQLSTATE 코드, 힌트, 로그 전용 상세 정보 등 풍부한 보조 데이터를 추가할 수 있어 에러 처리를 구조화하고 국제화를 지원한다. 번역이 필요 없고 코드가 간단한 내부/디버그 메시지에는 `elog`를 사용할 수 있다. 객체 관련 보조 함수를 사용하면 애플리케이션이 에러 메시지 텍스트를 파싱하지 않고도 관련 데이터베이스 객체를 식별할 수 있어 자동화된 에러 처리에 유용하다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/error-message-reporting.html](https://www.postgresql.org/docs/current/error-message-reporting.html)

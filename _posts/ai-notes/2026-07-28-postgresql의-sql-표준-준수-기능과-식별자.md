---
title: "PostgreSQL의 SQL 표준 준수 기능과 식별자"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-28 07:21:53 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-07-28
sources:
  - https://www.postgresql.org/docs/current/features-sql-standard.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: PostgreSQL은 SQL 표준의 광범위한 기능 세트를 지원하며, 그 중 **식별자(Identifier)**는 E031 항목으로 정의된 델리미티드 식별자, 소문자 식별자, 트레일링 언더스코어와 같은 핵심 규칙을 포함한다.

### 개요
PostgreSQL은 SQL 표준에 대한 광범위한 준수를 자랑하는 데이터베이스 관리 시스템이다. 공식 문서의 'SQL Conformance' 부록에는 PostgreSQL이 지원하는 수백 개의 SQL 기능이 목록화되어 있으며, 각 기능은 고유한 식별자 코드와 설명, 코어 여부로 분류되어 있다. 이 체계는 PostgreSQL의 기능 범위와 표준 준수 수준을 객관적으로 이해하는 데 도움을 준다. 본문에서는 이 방대한 목록의 구조와, 그 중에서도 데이터베이스 객체의 이름을 규정하는 **식별자(Identifier)** 관련 표준 지원에 초점을 맞춘다.

## SQL 표준 준수 기능 목록의 구조
PostgreSQL 문서의 기능 목록은 체계적인 테이블 형식으로 제공된다. 각 행은 하나의 SQL 기능을 나타내며, 다음 네 가지 주요 열로 구성되어 있다.

| 열 이름 | 설명 | 예시 |
| :--- | :--- | :--- |
| **Identifier** | 해당 기능을 지칭하는 고유 코드. | `E031-01`, `F041` |
| **Core?** | 해당 기능이 SQL 표준의 'Core' 기능인지 여부. 'Core'는 필수 구현 항목을 의미한다. | `Core` |
| **Description** | 기능에 대한 간략한 설명. | `Delimited identifiers` |
| **Comment** | PostgreSQL의 구현에 관한 추가 설명이나 주의사항. | `trims trailing spaces from CHARACTER values before counting` |

이 목록은 **데이터 타입**(E011, E021), **기본 질의**(E051), **조인**(F041), **트랜잭션**(E151), **권한**(E081) 등 SQL의 모든 주요 영역을 포괄한다. 'Core'로 표시된 기능은 표준 SQL의 핵심 사양에 해당한다.

## 식별자(Identifier)에 대한 표준 지원
식별자는 테이블, 컬럼, 스키마 등 데이터베이스 객체의 이름을 짓는 규칙이다. PostgreSQL은 SQL 표준의 식별자 관련 규정을 **E031** 항목 아래에서 지원한다.

**E031 (Core) Identifiers**는 식별자에 대한 기본적인 표준 지원을 의미한다. 이는 세 가지 하위 항목으로 구체화된다.
*   **E031-01 (Core) Delimited identifiers**: 큰따옴표(`"`)로 둘러싸인 **델리미티드 식별자**를 지원한다. 이는 식별자가 SQL 예약어나 공백을 포함할 때 사용된다.
*   **E031-02 (Core) Lower case identifiers**: **소문자 식별자**를 지원한다. PostgreSQL은 기본적으로 대소문자를 구분하지 않는(unquoted) 식별자를 소문자로 처리한다.
*   **E031-03 (Core) Trailing underscore**: 식별자 이름 끝에 **언더스코어(`_`)**를 사용하는 것을 허용한다.

이러한 지원을 통해 PostgreSQL은 표준 SQL의 식별자 명명 규칙을 준수하며, 다양한 명명 요구사항을 수용할 수 있다.

## 그 외 주요 기능 카테고리 예시
식별자 외에도 PostgreSQL이 지원하는 주요 표준 기능 카테고리는 다음과 같다.
*   **기본 데이터 타입 및 연산**: 정수/실수 타입(E011), 문자 타입 및 함수(E021), 날짜/시간 타입(F051)에 대한 코어 지원.
*   **데이터 조작 및 질의**: `SELECT`, `GROUP BY`, `HAVING`(E051), 다양한 조인(F041), 서브쿼리(E061), 집계 함수(E091)를 포함한 완전한 질의 기능.
*   **무결성 제약 조건**: `PRIMARY KEY`, `FOREIGN KEY`, `CHECK`, `NOT NULL`(E141) 지원.
*   **트랜잭션 및 동시성**: `COMMIT`, `ROLLBACK`(E151) 및 `SERIALIZABLE` 이상의 다양한 트랜잭션 격리 수준(F111-F114) 지원.
*   **스키마 관리**: `CREATE/DROP SCHEMA/TABLE/VIEW`(F031, F311), `ALTER TABLE`(F033, F382-F388) 지원.
*   **고급 기능**: 재귀 쿼리(T131), 윈도우 함수(T611-T617), JSON/XML 지원(T803-T879, X010-X035) 등 현대적인 SQL 기능을 광범위하게 포함.

### 표준 확장 및 PostgreSQL의 구현 특이사항
PostgreSQL은 필수(Core) 기능을 넘어선 많은 **확장 기능**도 지원한다. 예를 들어, `F052`(Intervals and datetime arithmetic), `F531`(Temporary tables), `T071`(BIGINT data type) 등이 있다. 또한, **Comment** 열에는 PostgreSQL의 구현 세부사항이 드러나는데, 예를 들어 `E021-04`(CHARACTER_LENGTH 함수)의 경우 "CHARACTER 값의 뒤쪽 공백을 제거한 후 길이를 계산한다"고 명시하여 표준 동작을 구체적으로 설명하고 있다.

### 정리
PostgreSQL의 SQL 표준 준수 기능 목록은 데이터베이스의 능력을 체계적으로 파악할 수 있는 지도와 같다. **식별자(E031)**는 이 지도에서 객체 명명 규칙을 정의하는 중요한 좌표점이다. 이 목록을 통해 개발자는 PostgreSQL이 단순한 데이터 저장소가 아닌, 광범위한 SQL 표준과 고급 기능을 구현한 완전한 관계형 데이터베이스 관리 시스템임을 확인할 수 있다. 특정 기능의 표준 준수 여부나 구현 상세는 공식 문서의 해당 항목을 직접 참조하는 것이 가장 정확하다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/features-sql-standard.html](https://www.postgresql.org/docs/current/features-sql-standard.html)

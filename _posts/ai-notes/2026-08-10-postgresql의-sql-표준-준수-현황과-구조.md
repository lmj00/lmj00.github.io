---
title: "PostgreSQL의 SQL 표준 준수 현황과 구조"
layout: post
categories: ai-notes
type: study-note
date: 2026-08-10 06:40:26 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-08-10
sources:
  - https://www.postgresql.org/docs/current/features.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요
PostgreSQL은 최신 SQL 표준을 준수하는 것을 개발 목표로 삼고 있으며, 전통적인 기능이나 상식과 충돌하지 않는 범위 내에서 지속적으로 표준을 따르려 노력한다. SQL 표준은 기능 세트를 정의하고 있으며, PostgreSQL은 대부분의 주요 기능을 지원하지만 완벽한 준수는 아직 달성되지 않은 상태다. 이 글에서는 PostgreSQL의 SQL 표준 준수 접근 방식, 표준의 구조, 그리고 현재 지원 수준에 대해 공식 문서를 바탕으로 살펴본다.

## SQL 표준의 진화와 PostgreSQL의 접근법
SQL 표준의 공식 명칭은 **ISO/IEC 9075 "Database Language SQL"**이다. 표준은 수정되어 개정판이 주기적으로 발표되며, 2023년 최신 버전은 **SQL:2023**이다. 그 이전에는 SQL:2016, SQL:2011, SQL:2008 등이 있었다. 각 새 버전은 이전 버전을 대체하므로, 더 오래된 버전에 대한 준수 주장은 공식적인 효력이 없다.

PostgreSQL 개발은 전통적인 기능이나 상식과 모순되지 않는 한 최신 공식 표준 버전을 준수하는 것을 목표로 한다. 표준이 요구하는 많은 기능이 지원되지만, 때로는 약간 다른 문법이나 함수로 구현되기도 한다. 시간이 지남에 따라 표준 준수도는 더 높아질 것으로 기대된다.

초기 **SQL-92** 표준은 준수를 위해 Entry, Intermediate, Full의 세 가지 기능 세트를 정의했다. 대부분의 DBMS는 중간 및 전체 수준의 방대한 기능 세트가 너무 많거나 레거시 동작과 충돌하기 때문에 Entry 수준만 준수했다. **SQL:1999**부터는 세 가지 넓은 수준 대신 많은 개별 기능 세트를 정의하는 방식으로 바뀌었다. 이 중 큰 부분이 **"Core" 기능**으로, 모든 준수하는 SQL 구현체가 제공해야 한다. 나머지 기능들은 순수하게 선택 사항이다.

## SQL 표준의 파트별 구조와 PostgreSQL의 적용 범위
표준은 여러 **파트(Part)**로 나뉘며, 각각 약칭을 가지고 있다. PostgreSQL 코어는 다음 파트들을 커버한다.
.### PostgreSQL 코어가 커버하는 표준 파트
| 파트 번호 | 약칭 (공식 명칭) | PostgreSQL 적용 상태 |
|---|---|---|
| ISO/IEC 9075-1 | SQL/Framework (Framework) | 코어가 커버함 |
| ISO/IEC 9075-2 | SQL/Foundation (Foundation) | 코어가 커버함 |
| ISO/IEC 9075-9 | SQL/MED (Management of External Data) | 코어가 커버함 |
| ISO/IEC 9075-11 | SQL/Schemata (Information and Definition Schemas) | 코어가 커버함 |
| ISO/IEC 9075-14 | SQL/XML (XML-related specifications) | 코어가 커버함 |

다른 파트들은 다음과 같은 상태다.
*   **Part 3 (SQL/CLI)**: ODBC 드라이버에 의해 커버되지만, 정확한 준수 여부는 현재 검증되지 않았다.
*   **Part 13 (SQL/JRT)**: PL/Java 플러그인에 의해 커버되지만, 마찬가지로 정확한 준수는 검증되지 않았다.
*   **Part 4, 10, 15, 16**: 현재 PostgreSQL용 구현체가 존재하지 않는다.

## 현재 PostgreSQL의 SQL:2023 준수 수준
PostgreSQL은 **SQL:2023**의 주요 기능 대부분을 지원한다. 전체 Core 준수를 위해 요구되는 177개의 필수 기능 중, PostgreSQL은 **적어도 170개**에 준수한다. 또한 지원되는 선택 기능의 목록도 길다. 문서 작성 시점을 기준으로, 어떤 데이터베이스 관리 시스템의 현재 버전도 SQL:2023 Core에 대한 완전한 준수를 주장하지 않는다는 점은 주목할 만하다.

공식 문서의 부록 D에는 PostgreSQL이 지원하는 기능 목록과 SQL:2023에 정의되었지만 아직 PostgreSQL에서 지원되지 않는 기능 목록이 제공된다. 그러나 이 두 목록은 근사치일 뿐이다. 지원된다고 나열된 기능에 비준수인 사소한 세부 사항이 있을 수 있고, 지원되지 않는다고 나열된 기능의 많은 부분이 실제로 구현되어 있을 수도 있다. 가장 정확한 정보는 문서의 본문에 포함되어 있다.

> 한 줄 요약: PostgreSQL은 SQL 표준, 특히 최신 SQL:2023의 Core 기능 대부분(170/177개)을 지원하며, 표준의 여러 파트(1,2,9,11,14)를 커버하지만 완벽한 준수는 아직 달성되지 않았다.

### 지원 및 미지원 기능 목록의 해석 주의사항
문서에 제공되는 지원/미지원 기능 목록을 해석할 때는 몇 가지 세부 규칙을 알아야 한다.
*   **하위 기능(Subfeature) 처리**: 기능 코드에 하이픈(`-`)이 포함된 것은 **하위 기능**을 의미한다. 따라서 특정 하위 기능이 지원되지 않으면, 다른 하위 기능이 지원되더라도 주 기능은 지원되지 않는 것으로 목록에 표시된다.
*   **정확성의 원천**: 기능의 작동 여부에 대한 가장 정확한 정보는 항상 문서의 본문에 있다. 부록의 목록은 참고용 근사치다.

### 정리
1.  PostgreSQL은 최신 SQL 표준 준수를 지향하지만, 전통과의 조화를 우선시한다.
2.  SQL 표준은 여러 파트로 구성되며, PostgreSQL 코어는 그중 Framework, Foundation, MED, Schemata, XML 파트를 직접 커버한다.
3.  SQL:2023 Core 필수 기능 177개 중 최소 170개를 지원하는 높은 준수 수준을 보이지만, 아직 완전한 준수는 이루어지지 않았다.
4.  공식 문서의 지원 기능 목록은 하위 기능 미지원 시 주 기능도 미지원으로 표시하는 등 근사치이므로, 정확한 판단은 본문 설명을 참고해야 한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/features.html](https://www.postgresql.org/docs/current/features.html)

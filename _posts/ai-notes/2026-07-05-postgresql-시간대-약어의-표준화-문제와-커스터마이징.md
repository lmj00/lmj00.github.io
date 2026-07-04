---
title: "PostgreSQL 시간대 약어의 표준화 문제와 커스터마이징"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-05 06:59:38 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-07-05
sources:
  - https://www.postgresql.org/docs/current/datetime-config-files.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: 시간대 약어는 표준화가 부족해 PostgreSQL은 IANA 데이터베이스와 커스텀 설정 파일을 통해 입력을 해석하며, 관리자는 `timezone_abbreviations` 파라미터와 `.../share/timezonesets/` 디렉토리의 파일을 통해 로컬 정책을 정의할 수 있다.

### 개요
시간대를 나타내는 약어(예: EST, PDT)는 잘 표준화되어 있지 않아 동일한 약어가 다른 지역에서 다른 오프셋을 의미하거나 역사적으로 그 의미가 변했을 수 있다. PostgreSQL은 이러한 **datetime 입력**에서의 약어 해석 문제를 해결하기 위해 두 가지 출처를 활용하는 유연한 시스템을 제공한다. 이 시스템의 핵심은 런타임 파라미터 `timezone`과 `timezone_abbreviations`이며, 데이터베이스 관리자는 커스텀 설정 파일을 통해 로컬 정책을 완전히 제어할 수 있다.

### 시간대 약어 해석의 두 가지 출처
PostgreSQL이 입력된 시간대 약어의 의미를 결정할 때 참조하는 두 가지 계층은 다음과 같다.

1.  **IANA 시간대 데이터베이스 (우선순위 높음)**
    *   `TimeZone` 런타임 파라미터(예: `America/New_York`)로 설정된 현재 시간대의 IANA 데이터를 먼저 확인한다.
    *   해당 지역에서 널리 사용되는 약어(예: `EST`는 UTC-5, `EDT`는 UTC-4)라면 IANA가 제공하는 의미를 우선적으로 인식한다.
    *   이 IANA 약어들은 `DateStyle` 설정에 따라 **datetime 출력**에서도 사용될 수 있다.

2.  **`timezone_abbreviations` 설정 파일**
    *   현재 IANA 시간대에서 약어를 찾지 못하면, `timezone_abbreviations` 파라미터로 지정된 목록에서 검색한다.
    *   이 목록의 주요 용도는 **현재 시간대가 아닌 다른 시간대의 약어를 입력에서 인식**할 수 있게 하는 것이다. 이 방식으로 정의된 약어는 출력에는 사용되지 않는다.
    *   어떤 데이터베이스 사용자도 이 파라미터 값을 변경할 수 있지만, 사용 가능한 값(설정 파일 이름)은 데이터베이스 관리자가 통제한다.

### 관리자 제어: 커스텀 약어 설정 파일
`timezone_abbreviations` 파라미터가 가리키는 값은 실제로 PostgreSQL 설치 디렉토리 내 `.../share/timezonesets/`에 저장된 **설정 파일의 이름**이다. 관리자는 이 디렉토리에 파일을 추가하거나 수정함으로써 시간대 약어에 대한 로컬 정책을 설정한다.

*   `timezone_abbreviations`는 `.../share/timezonesets/` 디렉토리 내에서 발견되는 **파일명이 완전히 알파벳으로만 구성된** 어떤 파일 이름으로도 설정할 수 있다. 점(.)과 같은 비알파벳 문자를 금지함으로써 의도된 디렉토리 밖의 파일이나 에디터 백업 파일 등을 읽는 것을 방지한다.
*   파일을 읽는 중 오류가 발생하면 새 값이 적용되지 않고 기존 세트가 유지된다. 데이터베이스 시작 중 오류가 발생하면 시작이 실패한다.
*   **주의사항**: 이 디렉토리의 파일을 수정하는 경우, 일반 데이터베이스 덤프에는 이 디렉토리가 포함되지 않으므로 백업은 관리자의 책임이다.

### 설정 파일 형식과 문법
시간대 약어 파일은 공백 줄과 `#`로 시작하는 주석을 포함할 수 있다. 비주석 줄은 다음 네 가지 형식 중 하나를 따라야 한다.

| 형식 | 설명 |
| :--- | :--- |
| `zone_abbreviation offset` | 약어와 UTC 기준 초 단위 오프셋(정수)을 정의. 양수는 동경, 음수는 서경. (예: `EST -18000`) |
| `zone_abbreviation offset D` | 위와 동일하지만, 해당 오프셋이 **일광 절약 시간(DST)** 을 나타냄을 표시. |
| `zone_abbreviation time_zone_name` | 약어를 IANA 시간대 데이터베이스에 정의된 `time_zone_name`(예: `America/Chicago`)과 연결. |
| `@INCLUDE file_name` | 동일 디렉토리(`.../share/timezonesets/`) 내의 다른 파일을 포함. 제한된 깊이까지 중첩 가능. |
| `@OVERRIDE` | 이 지시어 이후의 파일 항목이 이전 항목(일반적으로 포함된 파일에서 가져온 항목)을 **재정의(override)** 할 수 있도록 허용. 이 지시어 없이 동일 약어에 대한 정의가 충돌하면 오류로 처리됨. |

**오프셋 방식과 시간대 이름 방식의 선택 기준**
*   **단순 오프셋(`offset`)**: UTC와의 오프셋이 역사적으로 **한 번도 변하지 않은** 약어를 정의할 때 선호된다. 시간대 정의를 조회할 필요가 없어 처리 비용이 훨씬 저렴하다.
*   **시간대 이름(`time_zone_name`)**: 역사적으로 의미가 변했을 수 있는 약어를 다룰 때 필수적이다. PostgreSQL은 입력된 타임스탬프 값이 결정될 때 해당 약어가 그 시간대에서 사용되었는지, 그 당시 현재 사용 중이었는지, 아니면 그 직전 또는 이후의 의미를 조회하여 적절한 의미를 적용한다. 또한, 해당 약어가 실제로 그 시간대에 나타나지 않는 경우에도 정의할 수 있으며, 이 경우 약어 사용은 해당 시간대 이름을 직접 쓰는 것과 동등해진다.



### 기본 제공 파일과 주의사항
변경되지 않은 설치본에서는 몇 가지 기본 파일이 제공된다.
*   `Default`: 전 세계 대부분의 지역에 대한 비충돌 시간대 약어를 모두 포함.
*   `Australia`, `India`: 해당 지역용 파일로, 먼저 `Default` 파일을 포함(`@INCLUDE`)한 후 필요한 약어를 추가하거나 수정한다.
*   참조용 `Africa.txt`, `America.txt` 등: IANA 시간대 데이터베이스에 따라 사용 중으로 알려진 모든 시간대 약어 정보를 포함한다. 이 파일들의 정의를 커스텀 설정 파일에 복사해 사용할 수 있지만, 파일명에 점(.)이 포함되어 있어 `timezone_abbreviations` 설정으로 직접 참조할 수는 없다.

**중요한 주의사항**
커스텀 설정 파일에 정의된 시간대 약어는 PostgreSQL에 내장된 **비시간대 의미(non-timezone meanings)를 재정의(override)** 한다. 예를 들어, `Australia` 설정 파일은 `SAT`를 South Australian Standard Time으로 정의한다. 이 파일이 활성화되면, `SAT`는 '토요일(Saturday)'의 약어로 더 이상 인식되지 않는다.

### 정리
*   시간대 약어는 표준화가 미비하여 PostgreSQL은 IANA 데이터와 커스텀 설정 파일이라는 이중 계층으로 입력을 해석한다.
*   관리자는 `.../share/timezonesets/` 디렉토리의 파일을 통해 약어 정의를 완전히 제어할 수 있으며, `@INCLUDE`와 `@OVERRIDE` 문법으로 유연하게 구성할 수 있다.
*   역사적으로 변하지 않은 오프셋은 `offset`으로 정의하는 것이 효율적이며, 변한 오프셋은 IANA `time_zone_name`을 참조하는 방식이 필수적이다.
*   커스텀 정의는 내장된 약어(예: 요일) 의미를 재정의할 수 있으므로 주의가 필요하다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/datetime-config-files.html](https://www.postgresql.org/docs/current/datetime-config-files.html)

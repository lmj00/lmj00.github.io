---
title: "PostgreSQL의 Collation(정렬 규칙) 개념과 동작 원리"
layout: post
categories: ai-notes
type: study-note
date: 2026-08-21 06:32:51 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-08-21
sources:
  - https://www.postgresql.org/docs/current/collation.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요
**Collation**은 데이터 정렬 순서와 문자 분류 동작을 지정하는 기능이다. 데이터베이스 생성 이후 변경할 수 없는 `LC_COLLATE` 및 `LC_CTYPE` 설정의 제약을 완화해준다. 컬럼 단위 또는 심지어 연산 단위로 다른 정렬 규칙을 적용할 수 있어, 다국어 데이터 처리나 특정 로케일 요구사항이 있는 애플리케이션에서 중요하다.

### Collation의 기본 개념
**Collatable 데이터 타입**(`text`, `varchar`, `char` 및 사용자 정의 타입)을 가진 모든 표현식은 **Collation**을 가진다. 표현식의 Collation은 다음과 같이 결정된다.
* 컬럼 참조: 해당 컬럼에 정의된 Collation.
* 상수: 해당 데이터 타입의 기본 Collation.
* 복잡한 표현식: 입력값들의 Collation으로부터 유도된다(아래 규칙 참조).

표현식의 Collation은 데이터베이스 로케일 설정을 의미하는 **"default"** 일 수 있고, 또는 결정되지 않은(indeterminate) 상태일 수 있다. 후자의 경우 정렬 연산 등 Collation 정보가 필요한 작업은 실패한다.

데이터베이스 시스템이 정렬이나 문자 분류를 수행할 때는 입력 표현식의 Collation을 사용한다. 이는 `ORDER BY` 절이나 `<` 같은 비교 연산자, `lower`, `upper`, `initcap` 같은 대소문자 변환 함수, 패턴 매칭 연산자, `to_char` 함수 등에서 발생한다.

### Collation 유도(Collation Derivation)와 결합 규칙
Collation 유도는 **명시적(explicit)** 또는 **암시적(implicit)** 이다. `COLLATE` 절을 사용하면 명시적 유도이며, 그 외는 모두 암시적 유도이다. 함수 호출 등에서 여러 Collation이 결합될 때 다음 규칙이 적용된다.

1. **명시적 Collation이 있는 경우**: 입력 표현식 중 명시적으로 유도된 Collation이 있다면, 그들 모두는 동일해야 하며, 그 Collation이 결합 결과가 된다. 서로 다르면 오류가 발생한다.
2. **암시적 Collation만 있는 경우**: 모든 입력 표현식이 동일한 암시적 Collation 또는 default Collation을 가져야 한다. default가 아닌 Collation이 있으면 그것이 결합 결과가 된다. 모두 default면 결과는 default Collation이다.
3. **충돌하는 암시적 Collation이 있는 경우**: 결합 결과는 **indeterminate**(결정되지 않음) 상태가 된다. 이 상태 자체는 오류가 아니지만, 해당 연산(예: `<`)이 Collation을 알아야 한다면 런타임에 오류가 발생한다.

![diagram](/assets/diagrams/2026-08-21-postgresql의-collation-정렬-규칙-개념과-동작-원리-1.svg)

예를 들어, `a text COLLATE "de_DE"`, `b text COLLATE "es_ES"` 컬럼이 있는 테이블에서:
* `SELECT a < 'foo'`: `de_DE` 규칙 적용 (암시적 `de_DE` + default).
* `SELECT a < ('foo' COLLATE "fr_FR")`: `fr_FR` 규칙 적용 (명시적 우선).
* `SELECT a < b`: 오류 발생 (충돌하는 암시적 Collation). `a < b COLLATE "de_DE"`와 같이 명시적 지정으로 해결 가능.
* `SELECT a || b`: 오류 없음. `||` 연산자는 Collation에 무관하기 때문이다. 그러나 `ORDER BY a || b`는 `ORDER BY` 절이 Collation을 필요로 하므로 오류가 발생한다.

함수나 연산자의 결합 입력 표현식에 할당된 Collation은, 해당 함수/연산자의 결과가 collatable 데이터 타입일 경우 그 결과의 Collation으로도 간주된다.

### Collation 객체와 제공자(Provider)
Collation은 운영체제에 설치된 라이브러리가 제공하는 로케일을 SQL 이름에 매핑하는 **SQL 스키마 객체**이다. Collation 정의에는 로케일 데이터를 제공하는 라이브러리를 지정하는 **`provider`** 가 있다.

| 제공자(Provider) | 설명 | 주요 특징 |
| :--- | :--- | :--- |
| **`libc`** | 운영체제 C 라이브러리(`setlocale()`)가 제공하는 로케일 사용. | `LC_COLLATE`와 `LC_CTYPE` 설정의 조합에 매핑됨. **인코딩에 종속적** (동일 이름도 인코딩마다 별도 객체). |
| **`icu`** | 외부 ICU 라이브러리 사용. 빌드 시 ICU 지원이 구성되어야 함. | `LC_COLLATE`/`LC_CTYPE` 구분 없음. **인코딩에 독립적** (데이터베이스 내 동일 이름 객체는 하나). |

`libc` Collation은 주로 정렬 순서를 제어하는 `LC_COLLATE` 설정을 위한 것이지만, `LC_CTYPE`(문자 분류)도 함께 설정하는 것이 편리하므로 하나의 개념으로 통합되었다.

### 표준 및 사전 정의된 Collation
모든 플랫폼에서 지원되는 표준 Collation은 다음과 같다.

| Collation 이름 | 설명 | 제공자 | 인코딩 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **`unicode`** | Unicode Collation Algorithm(UCA) 사용. | ICU | 모든 인코딩 | ICU 루트 로케일(`und-x-icu`)과 동일. |
| **`ucs_basic`** | Unicode 코드 포인트 값으로 정렬. ASCII A-Z만 글자로 취급. | libc | `UTF8` only | `UTF8` 인코딩에서 `C` 로케일과 동일. |
| **`pg_unicode_fast`** | 코드 포인트 값 정렬. `lower`/`upper` 등에 Unicode 전체 대소문자 매핑 사용. | libc | `UTF8` only | 동작이 효율적이고 메이저 버전 내 안정적. |
| **`pg_c_utf8`** | 코드 포인트 값 정렬. `lower`/`upper` 등에 Unicode 단순 대소문자 매핑 사용. | libc | `UTF8` only | 동작이 효율적이고 메이저 버전 내 안정적. |
| **`C`** (또는 `POSIX`) | 바이트 값으로 정렬. ASCII A-Z만 글자로 취급. | libc | 데이터베이스 인코딩 | "전통적인 C" 동작. 인코딩별 동작 다를 수 있음. |
| **`default`** | 데이터베이스 생성 시 지정된 로케일 선택. | - | 데이터베이스 인코딩 | |

`initdb`는 데이터베이스 클러스터 초기화 시 운영체제(`locale -a`) 또는 ICU에서 발견한 모든 로케일을 기반으로 시스템 카탈로그 `pg_collation`을 채운다. `libc` 제공자의 경우 `de_DE.utf8` 같은 이름의 Collation을 생성하며, `.utf8` 태그가 제거된 `de_DE` 이름도 함께 생성해 사용을 권장한다(인코딩 변경 시 유리). ICU 제공자의 경우 BCP 47 언어 태그 형식에 `-x-icu` 접미사를 붙인 이름(예: `de-x-icu`, `de-AT-x-icu`)으로 생성된다.

### Collation 생성 및 관리
표준 및 사전 정의된 Collation(`pg_catalog` 스키마)으로 부족할 경우 사용자는 `CREATE COLLATION` 명령으로 자신의 Collation 객체를 생성할 수 있다. 사용자 정의 Collation은 사용자 스키마에 생성되어 `pg_dump`로 저장되어야 한다.

* **`libc` Collation 생성**: `CREATE COLLATION german (provider = libc, locale = 'de_DE');`
* **`ICU` Collation 생성**: `CREATE COLLATION german (provider = icu, locale = 'de-DE');` (BCP 47 언어 태그 사용)
* **기존 Collation 복사 생성**: `CREATE COLLATION german FROM "de_DE";` 호환성 이름 생성에 유용.

운영체제가 업그레이드되어 새 로케일 정의가 추가된 경우 `pg_import_system_collations()` 함수를 사용해 대량으로 가져올 수 있다.

### 결정적(Deterministic) vs 비결정적(Nondeterministic) Collation
Collation은 **결정적** 또는 **비결정적**일 수 있다.
* **결정적 Collation**: 바이트 시퀀스가 동일한 문자열만 동일하다고 판단한다.
* **비결정적 Collation**: 서로 다른 바이트를 가진 문자열도 동일할 수 있다고 판단할 수 있다(예: 대소문자 무시, 악센트 무시, 다른 Unicode 정규형 비교). 실제 무감각(insensitive) 비교 구현은 Collation 제공자에 달려 있으며, 결정적 플래그는 동점 처리 시 바이트 단위 비교 사용 여부만 결정한다.

### 주의사항 및 고려점
* **인코딩 종속성**: `libc` Collation은 인코딩에 종속적이다. 동일 데이터베이스 내에서만 `de_DE` 같은 단순화된 이름이 고유하다. `default`, `C`, `POSIX` Collation은 데이터베이스 인코딩에 관계없이 사용 가능하다.
* **Collation 호환성**: PostgreSQL은 동일한 속성을 가진 Collation 객체라도 **서로 다른 객체로 간주하여 호환되지 않는다**. 예를 들어, `COLLATE "C"`와 `COLLATE "POSIX"`는 동일한 동작을 하지만 함께 사용하면 오류가 발생한다. 따라서 단순화된 이름과 비단순화된 이름을 혼용하지 않는 것이 좋다.
* **ICU 지원 제한**: 일부(드물게 사용되는) 인코딩은 ICU에서 지원되지 않는다. 해당 인코딩의 데이터베이스에서는 ICU Collation 사용 시 오류가 발생한다.
* **성능과 안정성**: 추가 Collation의 효율성과 안정성은 제공자, 제공자 버전, 로케일에 따라 달라진다. `C`/`POSIX` Collation은 주어진 데이터베이스 인코딩 내에서는 효율적이고 안정적이다.

### 정리
* Collation은 데이터 정렬과 문자 처리 규칙을 세밀하게 제어하는 객체이다.
* Collation은 표현식에서 유도되며, 명시적(`COLLATE` 절)이 암시적보다 우선한다. 충돌 시 indeterminate 상태가 되어 오류를 유발할 수 있다.
* 제공자는 `libc`(인코딩 종속, OS 로케일)와 `icu`(인코딩 독립, 유연한 설정)로 구분된다.
* `C`, `default`, `unicode` 등 여러 표준 Collation이 존재하며, 필요시 `CREATE COLLATION`으로 생성할 수 있다.
* Collation 객체는 속성이 같아도 호환되지 않으므로 이름 관리에 주의해야 한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/collation.html](https://www.postgresql.org/docs/current/collation.html)

---
title: "PostgreSQL 파라미터 이름과 값: 다섯 가지 타입의 문법 규칙"
layout: post
interactive_design: true
categories: ai-notes
type: study-note
date: 2026-11-27 12:33:25 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-11-27
sources:
  - https://www.postgresql.org/docs/current/config-setting.html
  - https://www.postgresql.org/docs/19/config-setting.html
  - https://www.postgresql.org/docs/current/functions-admin.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: PostgreSQL 설정 파라미터의 이름은 대소문자를 구분하지 않으며, 값은 boolean·string·integer·floating point·enum 다섯 타입 중 하나로 주어지고 타입에 따라 허용되는 표기법이 달라진다.

### 개요
PostgreSQL의 모든 설정 파라미터는 이름이 대소문자를 구분하지 않는다. 각 파라미터가 받는 값은 boolean, string, integer, floating point, enum 다섯 가지 타입 중 하나이며, 이 타입이 값을 설정하는 문법을 결정한다. 따라서 파라미터 값을 올바르게 쓰려면 해당 파라미터의 타입을 알고 타입별 표기 규칙을 따라야 한다.

### 파라미터 이름과 값 타입
파라미터 이름은 대소문자에 관계없이 동일하게 취급된다. 값의 타입은 다섯 가지로 나뉘며, 각 타입은 고유한 설정 문법을 가진다. 아래 표는 다섯 타입의 값 표기와 핵심 규칙을 요약한다.

| 타입 | 값 표기 | 핵심 규칙 |
|---|---|---|
| boolean | `on`/`off`, `true`/`false`, `yes`/`no`, `1`/`0` | 대소문자 무관, 모호하지 않은 접두어 허용 |
| string | 작은따옴표로 감싼 문자열 | 값 내부의 작은따옴표는 두 개로 중복 |
| integer | 정수, `0x` 16진수, `0` 8진수 | 소수 값은 반올림, 천 단위 구분자 금지 |
| floating point | 부동소수점 숫자 | 일반 숫자 형식 |
| enum | 제한된 후보 값 중 하나 | string과 동일 표기, 대소문자 무관 |

### 타입별 값 문법
#### Boolean
boolean 값은 `on`, `off`, `true`, `false`, `yes`, `no`, `1`, `0`으로 쓸 수 있으며 모두 대소문자를 구분하지 않는다. 또한 이 단어들 중 하나의 모호하지 않은 접두어도 값으로 허용된다.

#### String
string 값은 일반적으로 작은따옴표로 감싸고, 값 안에 작은따옴표가 있으면 두 개로 중복해서 쓴다. 값이 단순한 숫자나 식별자라면 따옴표를 생략할 수 있지만, SQL 키워드와 일치하는 값은 일부 문맥에서 따옴표가 필요하다.

#### Numeric (integer와 floating point)
숫자 파라미터는 일반적인 정수·부동소수점 형식으로 지정한다. integer 타입이면 소수 값은 가장 가까운 정수로 반올림된다. integer 파라미터는 `0x`로 시작하는 16진수와 `0`으로 시작하는 8진수도 받지만, 이 형식에는 소수부를 쓸 수 없다. 천 단위 구분자는 사용하지 않으며, 16진수를 제외하면 따옴표가 필요 없다.

#### Enumerated
enum 파라미터는 string과 같은 방식으로 쓰지만 제한된 값 집합 중 하나만 허용한다. 허용되는 값은 `pg_settings` 뷰의 `enumvals` 열에서 확인할 수 있고, 값은 대소문자를 구분하지 않는다.



{% raw %}
<figure class="ai-scene"><figcaption>같은 입력 1.5, 타입이 저장 값을 결정한다 · 설명용 시각화</figcaption><iframe class="ai-scene-frame" src="/assets/generated/designs/2026-11-27-postgresql-파라미터-이름과-값-다섯-가지-타입의-문법-규칙-cd843346cf78e28b-1.html" title="같은 입력 1.5, 타입이 저장 값을 결정한다" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy" height="560"></iframe><p class="ai-scene-summary">설명용 입력 1.5를 사용한다. PostgreSQL 문서는 타입이 값 문법을 결정하며, integer 타입이면 소수 값이 가장 가까운 정수로 반올림된다고 설명한다.</p></figure>
{% endraw %}

### 단위가 있는 숫자 값
메모리나 시간의 양을 나타내는 일부 숫자 파라미터는 암묵적 단위를 가진다. 단위는 바이트, 킬로바이트, 블록(보통 8KB), 밀리초, 초, 분일 수 있다. 단위를 붙이지 않은 숫자 값은 `pg_settings` 뷰의 `unit` 열에서 확인할 수 있는 기본 단위를 사용한다.

편의를 위해 `'120 ms'`처럼 단위를 명시적으로 지정할 수 있으며, 이 값은 파라미터의 실제 단위로 변환된다. 단위를 쓰려면 값 전체를 문자열(따옴표 포함)로 작성해야 한다. 단위 이름은 대소문자를 구분하고, 숫자 값과 단위 사이에는 공백이 허용된다.

메모리 단위는 `B`(바이트), `kB`(킬로바이트), `MB`(메가바이트), `GB`(기가바이트), `TB`(테라바이트)이며 승수는 1000이 아닌 1024다. 시간 단위는 `us`(마이크로초), `ms`(밀리초), `s`(초), `min`(분), `h`(시간), `d`(일)이다.

단위와 함께 소수 값을 지정하면, 더 작은 단위가 존재할 경우 그 다음 작은 단위의 배수로 반올림된다. 예를 들어 `30.1 GB`는 `32319628902 B`가 아니라 `30822 MB`로 변환된다. integer 타입 파라미터라면 단위 변환 후 마지막에 정수로 반올림된다.

### 정리
PostgreSQL 파라미터 값은 다섯 가지 타입 중 하나로 주어지며, 타입이 곧 허용 문법을 결정한다. boolean과 enum은 대소문자를 구분하지 않는 반면, 단위 이름은 대소문자를 구분하고 단위 지정은 따옴표를 요구한다. 메모리 단위는 1024 승수를, 시간 단위는 `us`부터 `d`까지의 고정 목록을 사용하며, 단위 변환 시 소수 값은 다음 작은 단위의 배수로 반올림된다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/config-setting.html](https://www.postgresql.org/docs/current/config-setting.html)
> - [https://www.postgresql.org/docs/19/config-setting.html](https://www.postgresql.org/docs/19/config-setting.html)
> - [https://www.postgresql.org/docs/current/functions-admin.html](https://www.postgresql.org/docs/current/functions-admin.html)

---
title: "PostgreSQL VALUES: 디스크 없이 만드는 상수 테이블"
layout: post
interactive_design: true
categories: ai-notes
type: study-note
date: 2026-10-23 09:00:18 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-10-23
sources:
  - https://www.postgresql.org/docs/current/queries-values.html
  - https://www.postgresql.org/docs/current/sql-values.html
  - https://www.postgresql.org/docs/10/queries-values.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: `VALUES`는 값 식을 나열하는 것만으로 디스크에 테이블을 만들지 않고 쿼리 안에서 쓸 상수 테이블을 생성한다. `INSERT`의 데이터 소스로 가장 많이 쓰이며, `SELECT`가 허용되는 위치라면 어디서든 사용할 수 있다.

### 개요

`VALUES`는 쿼리 안에서 **상수 테이블(constant table)** 을 생성하는 기능이다. 실제 테이블을 디스크에 만들고 데이터를 적재하는 대신, 값 식의 나열만으로 쿼리에서 바로 사용할 수 있는 테이블 형태를 만든다. PostgreSQL 문서에 따르면 `VALUES`는 `INSERT` 명령의 데이터 소스로 가장 흔하게 쓰이고, 그다음으로는 서브쿼리 형태로 자주 사용된다. 핵심은 `VALUES`가 문법적으로 `SELECT`와 동등하게 취급되어, `SELECT`가 올 수 있는 자리라면 어디든 들어갈 수 있다는 점이다.

### 기본 문법: 행과 열이 결정되는 방식

`VALUES` 명령의 전체 구문은 다음과 같다.

```sql
VALUES (expression [, ...]) [, ...]
[ ORDER BY sort_expression [ ASC | DESC | USING operator ] [, ...] ]
[ LIMIT { count | ALL } ]
[ OFFSET start [ ROW | ROWS ] ]
[ FETCH { FIRST | NEXT } [ count ] { ROW | ROWS } ONLY ]
```

괄호로 묶인 표현식 리스트 하나가 테이블의 행 하나를 생성한다. 따라서 모든 리스트는 같은 수의 요소를 가져야 하며, 이 요소 수가 곧 테이블의 열 수가 된다. 또한 각 리스트에서 같은 위치에 있는 항목들은 서로 호환 가능한 데이터 타입이어야 한다. 결과 테이블의 각 열에 실제로 할당되는 타입은 `UNION`과 동일한 규칙으로 결정되는데, 해당 열에 등장한 표현식들의 명시적·추론된 타입을 결합해서 정해진다.

예를 들어 다음 명령은 두 개의 열과 세 개의 행으로 이루어진 테이블을 반환한다.

```sql
VALUES (1, 'one'), (2, 'two'), (3, 'three');
```

이 결과는 사실상 아래 `UNION ALL` 쿼리와 동등하다.

```sql
SELECT 1 AS column1, 'one' AS column2
UNION ALL
SELECT 2, 'two'
UNION ALL
SELECT 3, 'three';
```

PostgreSQL은 `VALUES` 테이블의 열 이름으로 기본적으로 `column1`, `column2` 등을 할당한다. 그런데 열 이름은 SQL 표준이 정해 놓은 것이 아니고 데이터베이스 시스템마다 다르게 동작하므로, 테이블 별칭 목록으로 기본 이름을 덮어쓰는 것이 좋다.

```sql
SELECT * FROM (VALUES (1, 'one'), (2, 'two'), (3, 'three')) AS t (num, letter);
```

### SELECT와 동등한 취급

문법적으로 `VALUES` 뒤에 표현식 리스트가 이어지는 형태는 `SELECT select_list FROM table_expression`과 동등하게 취급되며, `SELECT`가 허용되는 위치라면 어디든 사용할 수 있다. 예를 들어 `UNION`의 일부로 쓰거나, `ORDER BY`·`LIMIT`·`OFFSET`으로 구성되는 정렬 명세를 붙일 수 있다. 문법이 `VALUES`를 `SELECT`처럼 다루기 때문에, 단독으로 실행되는 `VALUES` 명령에도 `ORDER BY`, `LIMIT`(또는 동등한 `FETCH FIRST`), `OFFSET` 절을 붙일 수 있다.

`ORDER BY`의 정렬 표현식은 `column1`, `column2`처럼 `VALUES` 결과의 열을 참조하거나 정수 상수로 지정할 수 있다. `LIMIT`는 반환할 최대 행 수를, `OFFSET`은 행 반환을 시작하기 전에 건너뛸 행 수를 지정한다. 다만 `LIMIT`와 `OFFSET`은 PostgreSQL 확장이며, `VALUES` 자체는 SQL 표준을 따른다. 같은 설명이 PostgreSQL 10 문서에서도 확인되므로 이 문법의 핵심 동작은 오랫동안 유지되어 왔다.

### 주요 활용 예: INSERT, UPDATE, 서브쿼리

`VALUES`가 가장 많이 쓰이는 곳은 `INSERT`의 데이터 소스다.

```sql
INSERT INTO films (code, title, did, date_prod, kind)
VALUES ('T_601', 'Yojimbo', 106, '1961-06-16', 'Drama');
```

`INSERT` 최상위에 나타난 `VALUES` 리스트에서는 표현식 대신 `DEFAULT`를 써서 대상 열의 기본값이 들어가게 할 수 있다. `DEFAULT`는 `INSERT`가 아닌 다른 문맥에서는 사용할 수 없다.

```sql
INSERT INTO films VALUES
('UA502', 'Bananas', 105, DEFAULT, 'Comedy', '82 minutes'),
('T_601', 'Yojimbo', 106, DEFAULT, 'Drama', DEFAULT);
```

`VALUES`는 서브쿼리 자리에 그대로 들어갈 수도 있다. `FROM` 절에서 서브쿼리를 쓸 수 있는 자리에 `VALUES`를 두면 되며, 이때는 `SELECT`와 마찬가지로 `AS` 절이 필수다. `UPDATE`에서도 `FROM` 절의 임시 테이블로 사용해 조인 조건에 활용할 수 있다.

```sql
SELECT f.*
FROM films f, (VALUES('MGM', 'Horror'), ('UA', 'Sci-Fi')) AS t (studio, kind)
WHERE f.studio = t.studio AND f.kind = t.kind;
```

```sql
UPDATE employees SET salary = salary * v.increase
FROM (VALUES(1, 200000, 1.2), (2, 400000, 1.4)) AS v (depno, target, increase)
WHERE employees.depno = v.depno AND employees.sales >= v.target;
```

`AS` 절이 모든 열의 이름을 지정할 필요는 없지만, 그렇게 하는 것이 좋은 습관이다.

다음 다이어그램은 `VALUES`가 상수 테이블을 만들고 각 명령에서 소비되는 흐름을 보여준다.

![diagram](/assets/diagrams/2026-10-23-postgresql-values-디스크-없이-만드는-상수-테이블-1-e1a2e2af4845a744.svg)

### 타입 변환과 주의점

`INSERT` 안에서 쓰이는 `VALUES`는 특수한 경우다. 대상 테이블의 열 타입을 이미 알고 있으므로 `VALUES` 리스트를 스캔해 타입을 추론할 필요가 없고, 모든 값은 대상 열의 타입으로 자동 변환된다. 반면 다른 문맥에서 쓰일 때는 올바른 타입을 직접 지정해야 할 수 있다. 항목이 모두 따옴표로 감싼 리터럴 상수라면 첫 항목을 형변환하는 것만으로 나머지 항목들이 가정할 타입이 결정된다.

```sql
SELECT * FROM machines
WHERE ip_address IN (VALUES('192.168.0.1'::inet), ('192.168.0.10'), ('192.168.1.43'));
```

단순한 `IN` 테스트라면 `VALUES` 쿼리보다 스칼라 리스트 형태의 `IN`을 쓰는 편이 낫다. 작성할 내용이 적고 더 효율적인 경우가 많기 때문이다.

행 수가 매우 많은 `VALUES` 리스트는 피해야 한다. 메모리 부족 오류나 성능 저하가 발생할 수 있기 때문이다. 다만 `INSERT` 안에서는 대상 열 타입을 알 수 있어, 다른 문맥에서 실용적인 수준보다 더 큰 리스트를 처리할 수 있다.



{% raw %}
<figure class="ai-scene"><figcaption>같은 VALUES 리스트인데 문맥이 타입 처리를 가른다 · 설명용 시각화</figcaption><iframe class="ai-scene-frame" src="/assets/generated/designs/2026-10-23-postgresql-values-디스크-없이-만드는-상수-테이블-b1da26e3e0ab4753-1.html" title="같은 VALUES 리스트인데 문맥이 타입 처리를 가른다" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy" height="560"></iframe><p class="ai-scene-summary">PostgreSQL 문서의 `machines.ip_address`(inet) 예시 SQL을 바탕으로 표기했다. 값·표기는 설명용이며 실제 실행 결과가 아니다.</p></figure>
{% endraw %}

### 정리

`VALUES`는 값 표현식의 나열만으로 디스크에 테이블을 만들지 않는 상수 테이블을 생성하며, 괄호 리스트 하나가 행 하나가 되고 열 타입은 `UNION`과 같은 규칙으로 결정된다. 기본 열 이름은 `column1`, `column2` 등이지만 표준이 정한 이름이 아니므로 별칭으로 재지정하는 것이 좋다. `VALUES`는 문법적으로 `SELECT`와 동등하게 취급되어 `INSERT`, `UPDATE ... FROM`, 일반 서브쿼리 등 다양한 위치에서 쓰인다. 다만 행 수가 많은 리스트는 메모리 부족이나 성능 저하의 원인이 될 수 있으며, 값의 자동 변환과 더 큰 리스트 처리가 보장되는 것은 대상 열 타입을 아는 `INSERT` 문맥이다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/queries-values.html](https://www.postgresql.org/docs/current/queries-values.html)
> - [https://www.postgresql.org/docs/current/sql-values.html](https://www.postgresql.org/docs/current/sql-values.html)
> - [https://www.postgresql.org/docs/10/queries-values.html](https://www.postgresql.org/docs/10/queries-values.html)

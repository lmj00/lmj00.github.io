---
title: "PostgreSQL 쿼리와 SELECT 명령어 개요"
layout: post
categories: ai-notes
type: study-note
date: 2026-08-05 07:18:22 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-08-05
sources:
  - https://www.postgresql.org/docs/current/queries-overview.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요
데이터베이스에서 데이터를 검색하는 과정이나 명령을 **쿼리(query)**라고 한다. SQL에서 이 쿼리를 지정하는 데 사용되는 명령어가 `SELECT`이다. 이 글은 PostgreSQL에서 `SELECT` 명령어의 기본 구조와 핵심 구성 요소, 그리고 간단한 활용 방법을 개념적으로 설명한다.

### 쿼리와 SELECT 명령어의 기본 구조
`SELECT` 명령어의 일반적인 구문은 다음과 같다.
```sql
[WITH with_queries] SELECT select_list FROM table_expression [sort_specification]
```
이 구문은 크게 세 가지 핵심 부분으로 구성된다.
1.  **선택 목록(select_list)**: 조회할 열이나 계산식을 지정한다.
2.  **테이블 표현식(table_expression)**: 데이터를 가져올 대상(테이블, 조인, 서브쿼리 등)을 정의한다.
3.  **정렬 명세(sort_specification)**: 결과의 정렬 방식을 지정한다.

`WITH` 절은 고급 기능으로, 마지막에 다루어진다.

### 선택 목록(select_list)의 역할
선택 목록은 최종 결과에 어떤 데이터를 보여줄지 결정한다. 가장 단순한 형태는 별표(`*`)를 사용하여 테이블 표현식이 제공하는 **모든 사용자 정의 열**을 선택하는 것이다.
```sql
SELECT * FROM table1;
```
위 쿼리는 `table1`의 모든 행과 모든 열을 검색한다. 검색 결과의 표시 방법은 클라이언트 애플리케이션에 따라 다르다. 예를 들어, `psql` 프로그램은 화면에 ASCII-art 테이블을 표시하고, 클라이언트 라이브러리는 쿼리 결과에서 개별 값을 추출하는 함수를 제공한다.

선택 목록은 사용 가능한 열의 일부만 선택하거나, 열을 이용한 계산을 포함할 수 있다.
```sql
SELECT a, b + c FROM table1;
```
이 쿼리는 `table1`에서 `a` 열과 `b`와 `c` 열의 합계(단, `b`와 `c`가 수치형 데이터 타입일 경우)를 조회한다.

### 테이블 표현식(table_expression)의 범위
`FROM table1`은 가장 단순한 형태의 테이블 표현식으로, 단일 테이블을 읽는다. 일반적으로 테이블 표현식은 기본 테이블, 조인(join), 서브쿼리(subqueries)로 구성된 복잡한 구조가 될 수 있다.

흥미롭게도, 테이블 표현식을 완전히 생략하고 `SELECT` 명령을 계산기처럼 사용할 수도 있다.
```sql
SELECT 3 * 4;
SELECT random();
```
이 방식은 선택 목록의 표현식이 변동하는 결과를 반환할 때 유용하다. 예를 들어, `random()` 함수를 호출하는 데 사용할 수 있다.

### 정리
PostgreSQL에서 데이터 검색은 `SELECT` 명령어를 사용한 **쿼리**로 수행된다. 쿼리의 핵심은 **선택 목록**, **테이블 표현식**, **정렬 명세**라는 세 가지 구성 요소다. 선택 목록으로 원하는 열이나 계산식을 지정하고, 테이블 표현식으로 데이터 소스를 정의하며, 필요에 따라 결과를 정렬할 수 있다. `SELECT *`는 모든 열을 조회하는 간편한 방법이며, `FROM` 절 없이도 표현식 계산이나 함수 호출이 가능하다는 점이 특징이다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/queries-overview.html](https://www.postgresql.org/docs/current/queries-overview.html)

---
title: "PostgreSQL MVCC: 동시성 제어는 어떻게 동작하나"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-02
tags: [postgresql, mvcc, transaction, concurrency]
generated_by: "openrouter:google/gemma-4-26b-a4b-it:free"
generated_at: 2026-07-02
sources:
  - https://www.postgresql.org/docs/current/mvcc-intro.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요

PostgreSQL은 데이터에 대한 동시 접근을 관리하기 위해 **MVCC(Multiversion Concurrency Control)** 모델을 사용한다. 이 방식은 데이터의 일관성을 유지하면서도 다중 사용자 환경에서 성능을 최적화하기 위한 핵심 메커니즘이다. 각 SQL 문은 데이터의 현재 상태와 관계없이 특정 시점의 데이터 스냅샷을 바라보게 된다.

### MVCC의 동작 원리

**MVCC**는 데이터의 여러 버전을 유지하는 모델이다. 이를 통해 각 SQL 문은 일정 시간 전의 데이터 상태인 **데이터베이스 버전(database version)**을 스냅샷 형태로 보게 된다.

이러한 방식은 동일한 데이터 행을 업데이트하는 트랜잭션들이 동시에 존재하더라도, 각 세션이 일관되지 않은 데이터를 보는 것을 방지한다. 결과적으로 각 데이터베이스 세션에 대해 **트랜잭션 격리(transaction isolation)**를 제공한다.

![diagram](/assets/diagrams/2026-07-02-postgresql-mvcc-동시성-제어는-어떻게-동작하나-1.svg)

### MVCC와 락(Locking)의 차이점

전통적인 데이터베이스 시스템이 사용하는 락 방식과 달리, **MVCC**는 락 경합을 최소화하여 다중 사용자 환경에서 합리적인 성능을 보장한다. 가장 큰 장점은 읽기 작업과 쓰기 작업 사이의 충돌이 없다는 점이다.

| 구분 | MVCC 기반 동작 | 전통적인 락 방식 |
| :--- | :--- | :--- |
| **읽기 vs 쓰기** | 읽기가 쓰기를 차단하지 않으며, 쓰기도 읽기를 차단하지 않음 | 읽기 또는 쓰기 작업이 서로를 차단할 수 있음 |
| **성능** | 락 경합이 적어 일반적으로 더 높은 성능 제공 | 락 경합으로 인해 성능 저하 가능성 있음 |

PostgreSQL은 가장 엄격한 격리 수준인 **Serializable Snapshot Isolation (SSI)**를 제공할 때도 이러한 읽기/쓰기 간의 비차단(non-blocking) 보장을 유지한다.

### 기타 락 메커니즘

PostgreSQL은 **MVCC** 외에도 특정 상황을 위해 다음과 같은 락 기능을 추가로 제공한다.

* **테이블 및 행 수준 락(Table- and row-level locking)**: 완전한 트랜잭션 격리가 필요하지 않고, 특정 충돌 지점을 명시적으로 관리하고자 하는 애플리케이션을 위해 사용한다.
* **권고 락(Advisory locks)**: 애플리케이션이 정의하며, 단일 트랜잭션에 묶이지 않는 락을 획득할 수 있는 메커니즘을 제공한다.

다만, 일반적인 경우에는 **MVCC**를 적절히 사용하는 것이 락을 사용하는 것보다 더 나은 성능을 제공한다.

### 정리

PostgreSQL의 **MVCC**는 데이터의 스냅샷을 활용하여 읽기 작업이 쓰기 작업을 차단하지 않고, 쓰기 작업 또한 읽기 작업을 차단하지 않도록 설계되었다. 이를 통해 데이터 일관성과 트랜잭션 격리를 보장하면서도 다중 사용자 환경에서 높은 성능을 유지한다. 필요에 따라 테이블/행 수준 락이나 권고 락을 병행하여 사용할 수 있다.

---
> 🤖 작성 모델: `google/gemma-4-26b-a4b-it:free` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/mvcc-intro.html](https://www.postgresql.org/docs/current/mvcc-intro.html)

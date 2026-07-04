---
title: "PostgreSQL MVCC 동시성 제어의 핵심 개념"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-05 03:38:10 +0900
tags: [postgresql, mvcc]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-07-05
sources:
  - https://www.postgresql.org/docs/current/mvcc-intro.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요
PostgreSQL은 데이터에 대한 동시 접근을 관리하기 위해 **MVCC(Multiversion Concurrency Control)**라는 다중 버전 모델을 내부적으로 사용합니다. 이는 전통적인 데이터베이스 시스템의 잠금 방식과는 다른 접근법으로, 읽기와 쓰기 작업이 서로를 차단하지 않으면서도 일관된 데이터 스냅샷을 제공하는 것이 핵심입니다. 이 모델은 다중 사용자 환경에서도 합리적인 성능을 유지하는 데 기여합니다.

### MVCC의 기본 원리
MVCC의 핵심 아이디어는 각 SQL 문이 **특정 시점의 데이터 스냅샷**을 본다는 것입니다. 이는 데이터베이스 세션마다 **트랜잭션 격리**를 제공하는 기반이 됩니다. 예를 들어, 동시에 실행되는 여러 트랜잭션이 같은 데이터 행을 갱신하고 있어도, 각 문장은 그들에 의해 생성될 수 있는 불일치 데이터를 보지 않게 됩니다. 이는 데이터의 일관성을 유지하면서도 동시성을 높이는 방식입니다.

![diagram](/assets/diagrams/2026-07-05-postgresql-mvcc-동시성-제어의-핵심-개념-1.svg)

### MVCC의 주요 장점: 읽기와 쓰기의 비차단
MVCC 모델이 전통적인 잠금 방식보다 가지는 주요 이점은 **읽기 잠금과 쓰기 잠금이 충돌하지 않는다**는 점입니다. 이는 다음과 같은 중요한 보장을 의미합니다.
*   **읽기가 쓰기를 차단하지 않음 (Reads do not block writes)**
*   **쓰기가 읽기를 차단하지 않음 (Writes do not block reads)**

이러한 비차단 특성은 동시 처리 성능을 크게 향상시킵니다. PostgreSQL은 가장 엄격한 수준의 트랜잭션 격리인 **직렬화 가능 스냅샷 격리(Serializable Snapshot Isolation, SSI)**를 제공할 때도 이 보장을 유지합니다.

### 다른 잠금 메커니즘과의 관계
MVCC는 기본적인 동시성 제어 메커니즘이지만, PostgreSQL은 다양한 상황을 위한 다른 잠금 도구도 제공합니다.

*   **테이블 및 행 수준 잠금**: 완전한 트랜잭션 격리가 필요하지 않고, 특정 충돌 지점을 명시적으로 관리하고자 하는 애플리케이션을 위해 사용할 수 있습니다. 그러나 공식 문서는 MVCC의 적절한 사용이 일반적으로 잠금보다 더 나은 성능을 제공한다고 언급합니다.
*   **애플리케이션 정의 자문 잠금(Advisory Locks)**: 단일 트랜잭션에 묶이지 않는 잠금을 획득하는 메커니즘입니다. 이는 데이터베이스 객체가 아닌 애플리케이션 수준의 리소스에 대한 동기화를 위해 사용될 수 있습니다.

### 정리
PostgreSQL의 MVCC는 각 트랜잭션이 과거의 일관된 데이터 스냅샷을 보는 방식을 통해 동시성을 제어합니다. 이 모델의 가장 큰 강점은 읽기와 쓰기 작업이 서로를 차단하지 않아 다중 사용자 환경에서 높은 처리량을 가능하게 한다는 점입니다. MVCC는 기본적인 동시성 제어 방식으로 권장되며, 필요에 따라 테이블/행 잠금이나 자문 잠금과 같은 보조 도구를 함께 사용할 수 있습니다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/mvcc-intro.html](https://www.postgresql.org/docs/current/mvcc-intro.html)

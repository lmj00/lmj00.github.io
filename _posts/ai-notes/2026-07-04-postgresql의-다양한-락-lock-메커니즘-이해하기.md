---
title: "PostgreSQL의 다양한 락(Lock) 메커니즘 이해하기"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-04
tags: [postgresql, lock]
generated_by: "openrouter:google/gemma-4-26b-a4b-it:free"
generated_at: 2026-07-04
sources:
  - https://www.postgresql.org/docs/current/explicit-locking.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요

PostgreSQL은 테이블 내 데이터에 대한 동시 접근을 제어하기 위해 다양한 락 모드를 제공한다. 이는 MVCC(Multi-Version Concurrency Control)가 원하는 동작을 제공하지 못하는 상황에서 애플리케이션이 제어할 수 있는 락을 사용하기 위함이다. 또한 대부분의 PostgreSQL 명령은 실행 중 참조되는 테이블이 삭제되거나 호환되지 않는 방식으로 수정되는 것을 방지하기 위해 적절한 모드의 락을 자동으로 획득한다.

### 테이블 수준 락 (Table-Level Locks)

테이블 수준 락은 테이블 전체에 적용되는 락이다. 명칭에 "row"가 포함되어 있더라도 모두 테이블 수준의 락이며, 각 모드의 실질적인 차이는 어떤 락 모드와 충돌하느냐에 달려 있다. 두 트랜잭션은 동일한 테이블에 대해 서로 충돌하는 모드의 락을 동시에 보유할 수 없다.

락 모드 간의 충돌 관계는 다음과 같다.

| 요청된 락 모드 | ACCESS SHARE | ROW SHARE | ROW EXCL. | SHARE UPDATE EXCL. | SHARE | SHARE ROW EXCL. | EXCL. | ACCESS EXCL. |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ACCESS SHARE** | | X | | | | | | |
| **ROW SHARE** | | | X | | | | | |
| **ROW EXCL.** | | | | X | X | X | X | X |
| **SHARE UPDATE EXCL.** | | | X | X | X | X | X | X |
| **SHARE** | | | X | X | X | X | X | X |
| **SHARE ROW EXCL.** | | | X | X | X | X | X | X |
| **EXCL.** | | | X | X | X | X | X | X |
| **ACCESS EXCL.** | | X | X | X | X | X | X | X |

주요 테이블 락 모드와 사용 사례는 다음과 같다.

* **ACCESS SHARE**: `SELECT` 명령이 획득한다. 테이블을 수정하지 않고 읽기만 하는 쿼리가 사용한다. `ACCESS EXCLUSIVE` 락과만 충돌한다.
* **ROW SHARE**: `SELECT ... FOR UPDATE`, `FOR NO KEY UPDATE`, `FOR SHARE`, `FOR KEY SHARE` 옵션이 지정된 경우 획득한다.
* **ROW EXCLUSIVE**: `UPDATE`, `DELETE`, `INSERT`, `MERGE`와 같이 데이터를 수정하는 명령이 획득한다.
* **SHARE UPDATE EXCLUSIVE**: `VACUUM` (FULL 제외), `ANALYZE`, `CREATE INDEX CONCURRENTLY` 등이 사용하며, 스키마 변경이나 `VACUUM` 실행으로부터 테이블을 보호한다.
* **ACCESS EXCLUSIVE**: `DROP TABLE`, `TRUNCATE`, `REINDEX`, `CLUSTER`, `VACUUM FULL` 등이 사용한다. 모든 락 모드와 충돌하며, 해당 트랜잭션이 테이블에 접근하는 유일한 트랜잭션임을 보장한다.

락은 일반적으로 트랜잭션 종료 시까지 유지된다. 다만, 세이브포인트(savepoint) 이후에 획득한 락은 해당 세이브포인트로 롤백될 경우 즉시 해제된다.

### 행 수준 락 (Row-Level Locks)

행 수준 락은 데이터 쿼리에 영향을 주지 않으며, 동일한 행에 대한 **쓰기 작업과 락 획득 시도**를 차단한다. 행 수준 락의 충돌 관계는 아래와 같다.

![diagram](/assets/diagrams/2026-07-04-postgresql의-다양한-락-lock-메커니즘-이해하기-1.svg)

주요 행 수준 락 모드는 다음과 같다.

* **FOR UPDATE**: 해당 행을 수정, 삭제 또는 다른 `FOR UPDATE` 계열의 락을 시도하는 다른 트랜잭션을 차단한다.
* **FOR NO KEY UPDATE**: `FOR UPDATE`와 유사하지만, `SELECT FOR KEY SHARE` 명령을 차단하지 않는 더 약한 락이다.
* **FOR SHARE**: 공유 락을 획득한다. 다른 트랜잭션의 `UPDATE`, `DELETE`, `FOR UPDATE`, `FOR NO KEY UPDATE`는 차단하지만, `SELECT FOR SHARE`나 `SELECT FOR KEY SHARE`는 허용한다.
* **FOR KEY SHARE**: 가장 약한 락이다. `DELETE`나 키 값을 변경하는 `UPDATE`는 차단하지만, `SELECT FOR NO KEY UPDATE`, `SELECT FOR SHARE`, `SELECT FOR KEY SHARE`는 차단하지 않는다.

### 어드바이저리 락 (Advisory Locks)

어드바이저리 락은 시스템이 강제하는 것이 아니라 애플리케이션이 정의한 의미에 따라 사용하는 락이다. MVCC 모델에 맞지 않는 락킹 전략을 구현할 때 유용하며, 테이블에 플래그를 저장하는 방식보다 빠르고 테이블 비대화(bloat)를 피할 수 있다.

어드바이저리 락은 두 가지 수준으로 존재한다.

| 구분 | 세션 수준 (Session-level) | 트랜잭션 수준 (Transaction-level) |
| :--- | :--- | :--- |
| **해제 시점** | 명시적 해제 또는 세션 종료 시 | 트랜잭션 종료 시 자동 해제 |
| **트랜잭션 롤백** | 롤백되어도 락이 유지됨 | 롤백 시 락이 해제됨 |
| **특징** | 트랜잭션 의미를 따르지 않음 | 일반적인 락과 유사하게 동작함 |

### 데드락 (Deadlocks)

데드락은 두 개 이상의 트랜잭션이 서로가 보유한 락을 기다리며 무한히 대기하는 상태를 말한다. 이는 테이블 수준뿐만 아니라 행 수준 락에서도 발생할 수 있다.

PostgreSQL은 데드락 상황을 자동으로 감지하며, 관련 트랜잭션 중 하나를 강제로 중단(abort)시켜 문제를 해결한다. 데드락을 방지하기 위한 최선의 방법은 다음과 같다.

1. 여러 객체에 대해 락을 획득할 때 모든 애플리케이션이 **일관된 순서**로 락을 획득하도록 한다.
2. 트랜잭션 내에서 객체에 대해 처음 획득하는 락을 해당 객체에 필요한 **가장 엄격한 모드**로 설정한다.

### 정리

* PostgreSQL의 락은 테이블, 행, 페이지 수준으로 나뉘며, 각 모드에 따라 충돌 범위가 다르다.
* 테이블 수준 락은 명령의 성격에 따라 자동으로 획득되며, `ACCESS EXCLUSIVE`는 가장 강력한 제약을 가진다.
* 행 수준 락은 데이터 읽기에는 영향을 주지 않으나, 동일 행에 대한 쓰기 작업을 제어한다.
* 어드바이저리 락은 애플리케이션이 용도에 맞게 정의하여 사용하는 특수 락이다.
* 데드락 방지를 위해서는 락 획득 순서를 일관되게 유지하는 것이 중요하다.

---
> 🤖 작성 모델: `google/gemma-4-26b-a4b-it:free` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/explicit-locking.html](https://www.postgresql.org/docs/current/explicit-locking.html)

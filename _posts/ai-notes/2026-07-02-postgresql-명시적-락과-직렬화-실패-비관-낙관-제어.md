---
title: "PostgreSQL 명시적 락과 직렬화 실패: 비관/낙관 제어"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-02
tags: [postgresql, lock, transaction, mvcc]
generated_by: "openrouter:google/gemma-4-31b-it:free"
generated_at: 2026-07-02
sources:
  - https://www.postgresql.org/docs/current/explicit-locking.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: PostgreSQL의 명시적 락(Table, Row, Advisory)의 종류와 충돌 관계, 그리고 데드락 발생 시의 처리 메커니즘을 다룬다.

### 개요
PostgreSQL은 MVCC(Multi-Version Concurrency Control)가 제공하는 기본 동작만으로 부족한 상황에서 애플리케이션이 직접 동시 접근을 제어할 수 있도록 다양한 명시적 락 모드를 제공한다. 대부분의 명령어는 실행 중 참조 테이블이 삭제되거나 호환되지 않는 방식으로 수정되는 것을 방지하기 위해 자동으로 적절한 모드의 락을 획득한다. 현재 서버에서 유지되고 있는 락 목록은 `pg_locks` 시스템 뷰를 통해 확인할 수 있다.

### 테이블 수준 락 (Table-Level Locks)
테이블 수준 락은 `LOCK` 명령어로 명시적으로 획득할 수 있으며, 각 모드는 서로 충돌하는 락 모드 집합에 따라 구분된다. 충돌하는 모드의 락을 가진 두 트랜잭션은 동일한 테이블에 동시에 접근할 수 없다. 다만, 트랜잭션은 자기 자신과 충돌하지 않으므로, 하나의 트랜잭션이 `ACCESS EXCLUSIVE` 락을 획득한 후 동일 테이블에 `ACCESS SHARE` 락을 추가로 획득하는 것이 가능하다.

주요 테이블 수준 락 모드의 특성과 자동 획득 사례는 다음과 같다.

| 락 모드 | 충돌하는 모드 | 주요 자동 획득 사례 | 특징 |
| :--- | :--- | :--- | :--- |
| **ACCESS SHARE** | ACCESS EXCLUSIVE | `SELECT` | 단순 읽기 쿼리 시 획득 |
| **ROW SHARE** | EXCLUSIVE, ACCESS EXCLUSIVE | `SELECT ... FOR UPDATE/SHARE` 등 | 특정 옵션이 지정된 `SELECT` 시 획득 |
| **ROW EXCLUSIVE** | SHARE, SHARE ROW EXCL, EXCL, ACCESS EXCL | `UPDATE`, `DELETE`, `INSERT`, `MERGE` | 데이터 수정 명령어 시 획득 |
| **SHARE UPDATE EXCLUSIVE** | SHARE UPDATE EXCL, SHARE, SHARE ROW EXCL, EXCL, ACCESS EXCL | `VACUUM` (FULL 제외), `ANALYZE` 등 | 스키마 변경 및 `VACUUM` 실행 방지 |
| **SHARE** | ROW EXCL, SHARE UPDATE EXCL, SHARE ROW EXCL, EXCL, ACCESS EXCL | `CREATE INDEX` (CONCURRENTLY 제외) | 데이터 변경 방지 |
| **SHARE ROW EXCLUSIVE** | ROW EXCL, SHARE UPDATE EXCL, SHARE, SHARE ROW EXCL, EXCL, ACCESS EXCL | `CREATE TRIGGER`, 일부 `ALTER TABLE` | 데이터 변경 방지 및 세션당 하나만 유지 |
| **EXCLUSIVE** | ROW SHARE를 제외한 모든 모드 | `REFRESH MATERIALIZED VIEW CONCURRENTLY` | 읽기(`ACCESS SHARE`)만 병렬 진행 가능 |
| **ACCESS EXCLUSIVE** | 모든 모드 | `DROP TABLE`, `TRUNCATE`, `VACUUM FULL` 등 | 단일 트랜잭션만 테이블 접근 가능 |

획득한 락은 일반적으로 트랜잭션 종료 시까지 유지된다. 하지만 세이브포인트(savepoint) 설정 후 획득한 락은 세이브포인트 롤백 시 즉시 해제되며, PL/pgSQL 예외 블록 내에서 획득한 락 역시 에러로 인해 블록을 탈출할 때 해제된다.

### 행 수준 락 (Row-Level Locks)
행 수준 락은 데이터 쿼리 자체에는 영향을 주지 않으며, 동일한 행에 접근하려는 다른 쓰기 작업(writer)과 락 획득 시도자(locker)만 차단한다. 행 수준 락은 트랜잭션 종료 또는 세이브포인트 롤백 시 해제된다.

행 수준 락의 주요 모드와 동작 방식은 다음과 같다.

*   **FOR UPDATE**: 행을 수정, 삭제하거나 다른 트랜잭션이 락을 거는 것을 방지한다. `DELETE`나 특정 컬럼(외래 키에 사용 가능한 유니크 인덱스가 있는 컬럼)을 수정하는 `UPDATE` 시 자동으로 획득한다. `REPEATABLE READ` 또는 `SERIALIZABLE` 트랜잭션에서는 락을 걸려는 행이 트랜잭션 시작 이후 변경되었다면 에러가 발생한다.
*   **FOR NO KEY UPDATE**: `FOR UPDATE`와 유사하지만 더 약한 락으로, 동일 행에 대한 `SELECT FOR KEY SHARE` 명령을 차단하지 않는다. `FOR UPDATE` 락을 획득하지 않는 `UPDATE` 시 획득한다.
*   **FOR SHARE**: 공유 락을 획득하여 `UPDATE`, `DELETE`, `FOR UPDATE`, `FOR NO KEY UPDATE`를 차단하지만, `FOR SHARE`나 `FOR KEY SHARE`는 허용한다.
*   **FOR KEY SHARE**: 가장 약한 락으로, `DELETE`나 키 값을 변경하는 `UPDATE`, `FOR UPDATE`를 차단한다. 하지만 `FOR NO KEY UPDATE`, `FOR SHARE`, `FOR KEY SHARE`는 허용한다.

행 수준 락은 메모리에 수정된 행 정보를 저장하지 않으므로 락을 거는 행의 수에 제한은 없으나, `SELECT FOR UPDATE`와 같이 행을 마킹하는 작업은 디스크 쓰기를 유발할 수 있다.

### 데드락 (Deadlocks)
데드락은 두 개 이상의 트랜잭션이 서로가 가진 락을 기다리며 무한히 대기하는 상태를 말한다. 이는 명시적 락뿐만 아니라 행 수준 락으로 인해 발생할 수 있다.

![diagram](/assets/diagrams/2026-07-02-postgresql-명시적-락과-직렬화-실패-비관-낙관-제어-1.svg)

PostgreSQL은 데드락 상황을 자동으로 감지하여 관련된 트랜잭션 중 하나를 강제로 중단(abort)시켜 상황을 해결한다. 데드락을 방지하는 최선의 방법은 모든 애플리케이션이 객체에 접근하는 순서를 일관되게 유지하는 것이며, 처음 락을 획득할 때 필요한 가장 제한적인 모드를 사용하는 것이 권장된다.

### 자문 락 (Advisory Locks)
자문 락은 시스템이 강제하지 않고 애플리케이션이 정의한 의미에 따라 사용하는 락이다. MVCC 모델에 맞지 않는 비관적 락 전략을 구현할 때 유용하며, 테이블에 플래그를 저장하는 방식보다 빠르고 테이블 팽창(bloat)을 방지하며 세션 종료 시 자동으로 정리된다.

자문 락의 획득 방식은 두 가지로 나뉜다.

1.  **세션 수준 (Session-level)**: 명시적으로 해제하거나 세션이 종료될 때까지 유지된다. 트랜잭션 세맨틱을 따르지 않으므로, 트랜잭션 롤백 후에도 락이 유지되며 해제 명령은 이후 트랜잭션 실패 여부와 상관없이 유효하다.
2.  **트랜잭션 수준 (Transaction-level)**: 일반 락과 유사하게 트랜잭션 종료 시 자동으로 해제되며, 명시적인 해제 작업이 없다.

자문 락과 일반 락은 모두 공유 메모리 풀에 저장되며, 그 크기는 `max_locks_per_transaction`과 `max_connections` 설정에 의해 결정된다. 이 메모리가 고갈되면 서버가 더 이상 락을 부여할 수 없으므로 주의가 필요하다.

### 제약 사항 및 주의사항
*   **대기 시간**: 데드락이 감지되지 않는 한, 테이블 또는 행 수준 락을 요청한 트랜잭션은 충돌하는 락이 해제될 때까지 무한히 대기한다. 따라서 사용자 입력을 기다리는 등 트랜잭션을 장시간 열어두는 것은 위험하다.
*   **메모리 제한**: 자문 락을 포함한 모든 락은 공유 메모리를 사용하므로, 설정값에 따라 부여 가능한 락의 최대 수(수만에서 수십만 개)에 제한이 있다.

### 정리
PostgreSQL은 테이블, 행, 자문 락이라는 세 가지 수준의 명시적 락을 통해 동시성을 제어한다. 테이블 락은 모드별 충돌 관계가 엄격하며, 행 락은 쓰기 작업 간의 충돌을 제어한다. 자문 락은 애플리케이션의 필요에 따라 세션 또는 트랜잭션 단위로 유연하게 사용할 수 있다. 데드락 발생 시 시스템이 자동으로 한 트랜잭션을 중단시켜 해결하지만, 근본적으로는 일관된 락 획득 순서를 유지하는 설계가 중요하다.

---
> 🤖 작성 모델: `google/gemma-4-31b-it:free` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/explicit-locking.html](https://www.postgresql.org/docs/current/explicit-locking.html)

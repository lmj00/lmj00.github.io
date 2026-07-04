---
title: "PostgreSQL 명시적 락의 종류와 교착 상태 관리"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-05 03:47:30 +0900
tags: [postgresql, lock]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-07-05
sources:
  - https://www.postgresql.org/docs/current/explicit-locking.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: PostgreSQL은 MVCC로 처리되지 않는 동시성 제어를 위해 애플리케이션에서 직접 사용할 수 있는 테이블, 행, 페이지 수준의 명시적 락을 제공하며, 락 모드 간 충돌 관계와 교착 상태 발생 원리 및 방지 방법을 이해해야 한다.

### 개요
PostgreSQL은 **MVCC(Multi-Version Concurrency Control)** 만으로는 원하는 동작을 보장하기 어려운 상황에서 애플리케이션이 직접 동시성 접근을 제어할 수 있도록 다양한 **락 모드**를 제공한다. 또한 대부분의 PostgreSQL 명령어는 실행 중 참조하는 테이블이 호환되지 않는 방식으로 삭제되거나 수정되는 것을 방지하기 위해 적절한 모드의 락을 자동으로 획득한다. 현재 데이터베이스 서버에서 유지 중인 락의 목록은 `pg_locks` 시스템 뷰를 통해 확인할 수 있다.

### 테이블 수준 락
테이블 수준 락은 `LOCK` 명령으로 명시적으로 획득할 수 있으며, 여러 SQL 명령어에 의해 자동으로 사용된다. 모든 락 모드는 이름에 "행(row)"이 포함되어 있어도 **테이블 수준**이다. 각 락 모드의 실질적인 차이는 **서로 충돌하는 락 모드의 집합**에 있다. 두 트랜잭션이 동일한 테이블에 대해 충돌하는 모드의 락을 동시에 보유할 수 없다. 단, 트랜잭션은 자기 자신과는 충돌하지 않는다(예: `ACCESS EXCLUSIVE` 락을 획득한 후 동일 테이블에 `ACCESS SHARE` 락을 획득 가능). 충돌하지 않는 락 모드는 여러 트랜잭션에 의해 동시에 보유될 수 있다.

아래 표는 각 락 모드가 자동으로 사용되는 명령어와 주요 특징을 정리한 것이다.

| 락 모드 (내부 이름) | 주요 사용 명령어/맥락 | 특징 및 충돌 범위 |
| :--- | :--- | :--- |
| **ACCESS SHARE** (`AccessShareLock`) | `SELECT` (읽기 전용 쿼리) | `ACCESS EXCLUSIVE`와만 충돌. 가장 제한이 적음. |
| **ROW SHARE** (`RowShareLock`) | `SELECT ... FOR UPDATE`, `FOR NO KEY UPDATE`, `FOR SHARE`, `FOR KEY SHARE` | `EXCLUSIVE`, `ACCESS EXCLUSIVE`와 충돌. |
| **ROW EXCLUSIVE** (`RowExclusiveLock`) | `UPDATE`, `DELETE`, `INSERT`, `MERGE` | `SHARE`, `SHARE ROW EXCLUSIVE`, `EXCLUSIVE`, `ACCESS EXCLUSIVE`와 충돌. 데이터 수정 명령이 획득. |
| **SHARE UPDATE EXCLUSIVE** (`ShareUpdateExclusiveLock`) | `VACUUM`(without `FULL`), `ANALYZE`, `CREATE INDEX CONCURRENTLY`, 일부 `ALTER TABLE` | 동시 스키마 변경과 `VACUUM` 실행을 보호. `SHARE` 이상의 강한 락들과 충돌. |
| **SHARE** (`ShareLock`) | `CREATE INDEX` (without `CONCURRENTLY`) | 동시 데이터 변경을 보호. `ROW EXCLUSIVE` 이상의 락들과 충돌. |
| **SHARE ROW EXCLUSIVE** (`ShareRowExclusiveLock`) | `CREATE TRIGGER`, 일부 `ALTER TABLE` | 동시 데이터 변경을 보호하며, **자기 배타적**이어서 한 세션만 보유 가능. |
| **EXCLUSIVE** (`ExclusiveLock`) | `REFRESH MATERIALIZED VIEW CONCURRENTLY` | 동시 `ACCESS SHARE`(읽기) 락만 허용. `ROW SHARE` 이상의 거의 모든 락과 충돌. |
| **ACCESS EXCLUSIVE** (`AccessExclusiveLock`) | `DROP TABLE`, `TRUNCATE`, `REINDEX`, `VACUUM FULL`, `REFRESH MATERIALIZED VIEW` (without `CONCURRENTLY`), 많은 `ALTER` 명령, 명시적 모드 없는 `LOCK TABLE`의 기본 모드 | **모든 모드의 락과 충돌**. 보유 트랜잭션이 테이블에 대한 유일한 접근자임을 보장. `SELECT`(without `FOR UPDATE/SHARE`)을 블록하는 유일한 락. |

락은 일반적으로 트랜잭션 종료 시까지 유지된다. 그러나 **세이브포인트**를 설정한 후 획득한 락은 해당 세이브포인트로 롤백될 경우 즉시 해제된다. `PL/pgSQL` 예외 블록 내에서 획득한 락도 블록을 빠져나오는 오류 발생 시 해제된다.

### 행 수준 락
행 수준 락은 테이블 수준 락에 추가적으로 존재하며, 동일한 행에 대한 **작성자와 다른 락 획득자만을 블록**한다. 데이터 조회에는 영향을 주지 않는다. 행 수준 락도 트랜잭션 종료 시 또는 세이브포인트 롤백 시 해제된다.

PostgreSQL은 메모리에 수정된 행에 대한 정보를 저장하지 않으므로 **한 번에 잠글 수 있는 행의 수에는 제한이 없다**. 그러나 행을 잠그는 것은 선택된 행을 잠금 표시하기 위해 수정해야 하므로 디스크 쓰기를 유발할 수 있다.

행 수준 락 모드와 그 충돌 관계는 다음과 같다.

| 요청된 락 모드 | 현재 보유 중인 락 모드와의 충돌 여부 |
| :--- | :--- |
| **FOR KEY SHARE** | `FOR UPDATE`와 충돌 |
| **FOR SHARE** | `FOR UPDATE`, `FOR NO KEY UPDATE`와 충돌 |
| **FOR NO KEY UPDATE** | `FOR UPDATE`, `FOR SHARE`, `FOR NO KEY UPDATE`와 충돌 |
| **FOR UPDATE** | 모든 모드(`FOR KEY SHARE`, `FOR SHARE`, `FOR NO KEY UPDATE`, `FOR UPDATE`)와 충돌 |

각 모드의 세부 동작은 다음과 같다.
- **`FOR UPDATE`**: 선택된 행이 **업데이트된 것처럼** 잠근다. 다른 트랜잭션이 이 행을 `UPDATE`, `DELETE`, `SELECT FOR UPDATE`, `SELECT FOR NO KEY UPDATE`, `SELECT FOR SHARE`, `SELECT FOR KEY SHARE` 하는 것을 현재 트랜잭션 종료 시까지 블록한다. `DELETE` 명령과, 외래 키로 사용될 수 있는 고유 인덱스가 있는 컬럼 값을 수정하는 `UPDATE` 명령도 이 모드의 락을 획득한다.
- **`FOR NO KEY UPDATE`**: `FOR UPDATE`와 유사하지만 더 약한 락이다. 동일한 행에 대한 `SELECT FOR KEY SHARE` 명령을 블록하지 않는다. `FOR UPDATE` 락을 획득하지 않는 `UPDATE` 명령이 이 락을 획득한다.
- **`FOR SHARE`**: `FOR NO KEY UPDATE`와 유사하지만 **공유 락**을 획득한다. 다른 트랜잭션이 해당 행을 `UPDATE`, `DELETE`, `SELECT FOR UPDATE`, `SELECT FOR NO KEY UPDATE` 하는 것을 블록하지만, `SELECT FOR SHARE`나 `SELECT FOR KEY SHARE`는 허용한다.
- **`FOR KEY SHARE`**: `FOR SHARE`보다 더 약한 락이다. `SELECT FOR UPDATE`는 블록하지만 `SELECT FOR NO KEY UPDATE`는 블록하지 않는다. 다른 트랜잭션이 키 값을 변경하는 `DELETE`나 `UPDATE`를 수행하는 것을 블록하지만, 다른 `UPDATE`나 `SELECT FOR NO KEY UPDATE`, `SELECT FOR SHARE`, `SELECT FOR KEY SHARE`는 방해하지 않는다.

### 페이지 수준 락과 어드바이저리 락
**페이지 수준 락**은 공유 버퍼 풀 내의 테이블 페이지에 대한 읽기/쓰기 접근을 제어하는 데 사용되며, 행을 가져오거나 업데이트한 후 즉시 해제된다. 애플리케이션 개발자는 일반적으로 이 수준의 락을 신경 쓸 필요가 없다.

**어드바이저리 락(Advisory Locks)** 은 애플리케이션이 정의한 의미를 가진 락으로, 시스템이 강제하지 않고 애플리케이션이 올바르게 사용해야 한다. MVCC 모델에 잘 맞지 않는 락킹 전략(예: "플랫 파일" 시스템의 비관적 락킹 에뮬레이션)에 유용하다. 테이블의 플래그를 사용하는 것보다 빠르고, 테이블 부풀림을 방지하며, 세션 종료 시 서버에 의해 자동 정리된다.

획득 방법은 두 가지이다.
1.  **세션 수준**: 명시적으로 해제하거나 세션이 종료될 때까지 유지된다. 트랜잭션 롤백 시에도 유지되며, 롤백 후에도 해제되지 않는다.
2.  **트랜잭션 수준**: 일반 락 요청처럼 동작하며, 트랜잭션 종료 시 자동 해제된다. 명시적 해제 작업이 없다.

동일한 어드바이저리 락 식별자에 대한 세션 수준과 트랜잭션 수준 요청은 서로 예상대로 블록한다. 한 세션이 이미 특정 어드바이저리 락을 보유 중이라면, 다른 세션이 대기 중이더라도 해당 세션의 추가 요청은 항상 성공한다.

모든 락과 마찬가지로, 현재 보유 중인 어드바이저리 락 목록은 `pg_locks` 시스템 뷰에서 확인할 수 있다. 어드바이저리 락과 일반 락은 `max_locks_per_transaction` 및 `max_connections` 설정 변수로 정의된 공유 메모리 풀에 저장되므로, 이 메모리를 고갈시키지 않도록 주의해야 한다.

### 교착 상태와 주의사항
명시적 락 사용은 **교착 상태(Deadlock)** 발생 가능성을 높인다. 교착 상태는 두 개 이상의 트랜잭션이 각각 상대방이 원하는 락을 보유하고 있어 서로 진행하지 못하는 상태이다. PostgreSQL은 교착 상태를 자동으로 탐지하고 관련 트랜잭션 중 하나를 중단시켜 다른 트랜잭션이 완료되도록 한다.

![diagram](/assets/diagrams/2026-07-05-postgresql-명시적-락의-종류와-교착-상태-관리-1.svg)

**행 수준 락**에 의해서도 교착 상태가 발생할 수 있다(따라서 명시적 락을 사용하지 않아도 발생 가능). 예를 들어, 두 트랜잭션이 서로 다른 순서로 동일한 두 행을 업데이트하려 할 때 발생한다.

교착 상태에 대한 최선의 방어책은 **모든 애플리케이션이 데이터베이스의 여러 객체에 대해 일관된 순서로 락을 획득하도록 보장**하여 사전에 피하는 것이다. 또한 트랜잭션 내에서 객체에 대해 획득하는 첫 번째 락이 해당 객체에 필요로 할 가장 제한적인 모드가 되도록 해야 한다. 사전 검증이 어렵다면, 교착 상태로 인해 중단된 트랜잭션을 재시도하는 방식으로 처리할 수 있다.

교착 상태 상황이 탐지되지 않으면, 테이블 수준 또는 행 수준 락을 요청하는 트랜잭션은 충돌하는 락이 해제되기를 **무기한 대기**한다. 따라서 애플리케이션이 사용자 입력을 기다리는 등 **오랜 시간 동안 트랜잭션을 열어두는 것은 좋지 않은 방법**이다.

### 정리
PostgreSQL은 MVCC를 보완하는 다양한 명시적 락(테이블, 행, 페이지 수준)을 제공한다. 각 락 모드는 특정 SQL 명령에 의해 자동 획득되며, 충돌하는 모드 집합이 다르다. `ACCESS EXCLUSIVE`가 가장 강력하고 `ACCESS SHARE`가 가장 약하다. 행 수준 락은 `FOR UPDATE`가 가장 강하고 `FOR KEY SHARE`가 가장 약하다. 락은 트랜잭션 또는 세션(어드바이저리 락) 종료 시 해제된다. 명시적 락 사용은 교착 상태 가능성을 높이므로, 객체에 대한 락 획득 순서를 일관되게 유지하는 것이 최선의 예방책이다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/explicit-locking.html](https://www.postgresql.org/docs/current/explicit-locking.html)

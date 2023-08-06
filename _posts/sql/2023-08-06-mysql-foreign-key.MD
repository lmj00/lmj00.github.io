---
title: "MySQL Foreign Key"
layout: post
categories: sql
---  


### Foreign Key
> 참조 무결성을 지키기 위해 필요

> 개념적으로 존재한다고 해서 참조 무결성이 지켜지는 것이 아니다. Foreign Key를 지정해줘야만 참조 무결성을 지켜준다.

> 테이블에서는 Foreign Key도 제약 조건이다. 제약 조건 이름을 설정하지 않아도 MySQL에서 자동으로 붙여준다.

```sql
ALTER TABLE `테이블 이름`
ADD CONSTRAINT `제약 조건 이름`
FOREIGN KEY `(참조하는 컬럼)` REFERENCES `참조되는 테이블 이름` `(참조되는 컬럼)`;
```

<br>

예시
```sql
ALTER TABLE film_actor
ADD CONSTRAINT film_constraint
FOREIGN KEY (film_id) REFERENCES film (film_id);
```


### Foreign Key 삭제
```sql
ALTER TABLE `테이블 이름` DROP FOREIGN KEY `FOREIGN KEY 이름`
```

### 테이블 스키마 파악하기
```sql
SHOW CREATE TABLE `테이블 이름`;
```

---

### RESTRICT 정책
> 자신을 참조하고 있는 자식 테이블의 로우가 하나라도 있으면 부모 테이블의 로우를 삭제, 갱신할 수 없다.


### CASCADE 정책
> 부모 테이블 로우가 삭제, 갱신될 때, 참조하던 자식 테이블의 로우도 같이 삭제, 갱신됨


### SET NULL 정책
> 부모 테이블의 로우가 삭제, 갱신될 때, 참조하던 자식 테이블의 Foreign key 컬럼의 값을 NULL로 바꿈


`ON DELETE`와 `ON UPDATE`에서 서로 다른 정책을 설정할 수 있다.

---

### 물리적 Foreign Key
> 실제로 Foreign Key를 설정해서 제약 조건을 구현


### 논리적 Foreign Key
> 데이터베이스 설계 단계에서 사용되는 개념, 데이터의 의미와 관계를 설명하는데 중점


### 논리적 Foreign Key를 사용하는 이유
- 물리적 Foreign Key의 성능 저하
  - 인덱스 관리
  - 무결성 검사
  - 조인 연산
  - 복잡한 관계

<br>

- 데이터 일관성 유지
---
title: "MySQL Subquery, View"
layout: post
categories: sql
modified_date: 2023-06-18
--- 


### 서브쿼리
> SQL 문 안에 들어가는 SELECT 문

> 괄호로 서브 쿼리를 감싸줘야 한다.

 
### SELECT 절
```sql
SELECT 
...
(SELECT ...) 
FROM 테이블
```


### WHERE 절
```sql
SELECT
...
FROM 테이블
WHERE 컬럼 명 [Equi 또는 Non-Equi 조인] (SELECT ...)
```

```sql
SELECT amount
FROM payment 
WHERE amount = (SELECT MAX(amount) FROM payment)
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/314a88cf-0401-4f7b-86d5-e4608d0c2b96)

<br>

> 여러 로우의 값을 리턴하는 서브 쿼리로도 사용가능하다.

```sql
SELECT payment_id FROM payment
WHERE payment_id IN
(
SELECT customer_id FROM payment
GROUP BY customer_id HAVING AVG(amount) >= 4
)
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/b519316a-23aa-4f3e-bae0-4afeb8e8cf48)

<br>

> 서브 쿼리 결과

```sql
SELECT customer_id, AVG(amount)
FROM payment
GROUP BY customer_id 
HAVING AVG(amount) >= 4
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/8399bd04-e4d9-4c7b-8750-1546ad0e52dc)


### FROM 절
```sql
SELECT ... FROM (SELECT ...) AS 별칭
```
> 서브쿼리로 탄생한 테이블을 derived 테이블이라고 한다.

> derived 테이블에 alias를 꼭 붙여줘야 한다.

`derived` - 파생된 

---

### 서브쿼리에서 사용하는 연산자

### ANY, SOME
> 조건 중 하나라도 만족하면 TRUE

```sql
WHERE 컬럼 명 [Equi 또는 Non-Equi 조인] ANY(서브 쿼리)
```


### ALL
> 모든 조건을 만족해야 TRUE

```sql
WHERE 컬럼 명 [Equi 또는 Non-Equi 조인] ALL(서브 쿼리)
```

---

### 비상관 서브쿼리
> 서브쿼리 단독으로도 실행할 수 있는 독립적인 쿼리

  
### 상관 서브쿼리
> 외부 쿼리와 상관관계가 있는 서브쿼리, 단독으로 실행하지 못하는 쿼리

> 조인으로도 같은 결과를 얻을 수 있다. 직관적인 것을 사용하면 된다.

```sql
SELECT * FROM payment
WHERE EXISTS (SELECT * FROM customer WHERE customer_id = payment.customer_id)
```

> `(SELECT * FROM customer WHERE customer_id = payment.customer_id)`에서 필요한 payment<br> 테이블이 outer query에 적혀있으므로 단독으로 실행하지 못한다.


### EXISTS, NOT EXISTS
> 상관 서브쿼리에서 자주 사용하는 키워드

> 존재하면, 존재하지 않으면 

```sql
WHERE EXISTS (서브쿼리)
```

---

### 뷰
> 조인, 서브쿼리 등의 작업을 해서 만든 결과의 가상 테이블

> 서브쿼리 중첩을 해결할 수 있다.

> 필요한 컬럼이나 특정 로우들을 제외하고 테이블을 만들수 있기 때문에 데이터 보안을 제공한다.

```sql
CREATE VIEW 뷰 이름 AS SELECT ... 
```
```sql
CREATE VIEW film_v AS
SELECT film_id, title, release_year FROM film
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/df851f4d-eed7-4113-9369-467c4fc8d9ec)


### 데이터베이스 파악
```sql
SHOW DATABASES;
```

### 테이블의 컬럼 구조
```sql
DESCRIBE 테이블명
```

### 테이블, 뷰 파악
```sql
SHOW FULL TABLES IN DB명
```
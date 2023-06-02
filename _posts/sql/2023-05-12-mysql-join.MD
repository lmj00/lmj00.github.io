---
title: "MySQL JOIN"
layout: post
categories: sql
modified_date: 2023-06-02
--- 
 

### JOIN
> 여러 테이블 합쳐서 하나의 테이블로 보이게 해준다.

---

### 결합 연산
> 테이블을 가로 방향으로 합친다.


### LEFT OUTER JOIN
```sql
SELECT 
테이블1.컬럼,
테이블2.컬럼,
...
FROM 테이블1 LEFT OUTER JOIN 테이블2
ON 테이블1.id = 테이블2.id
```

> 테이블1에 테이블2를 ON 조건으로 합친다.

> 조건은 서로 값이 같은 로우끼리 연결

> 컬럼의 값이 NULL인 경우, 테이블2에 존재하지 않는 로우

<br>

> 총 금액 구하기

```sql
SELECT
    customer.customer_id,
    customer.last_name,
    SUM(payment.amount)
FROM customer LEFT OUTER JOIN payment
ON customer.customer_id = payment.customer_id
GROUP BY customer.customer_id
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/e12e014b-8fc1-454e-bcf7-eed35596b26d)


### RIGHT OUTER JOIN 
> LEFT OUTER JOIN과 반대

> 테이블2에 테이블1을 ON 조건으로 합친다.


### FULL OUTER JOIN
> LEFT OUTER JOIN의 결과와 RIGHT OUTER JOIN 결과를 합친다.

```sql
SELECT ...  LEFT OUTER JOIN ...
UNION
SELECT ...  RIGHT OUTER JOIN ...
```


### INNER JOIN
> 두 테이블 조건에 일치하는 컬럼 값이 있는 로우들만 합친다. 

> 기준 컬럼이 NULL이 되는 경우는 없다.

> OUTER JOIN과 다르게 기준이 되는 테이블이 없다.


### NATURAL JOIN
> 테이블에서 같은 이름의 컬럼을 찾아서 자동으로 조건으로 설정하고, INNER JOIN을 해준다.

```sql
FROM 테이블1 NATURAL JOIN 테이블2
```
> 테이블 구조 파악을 위해 NATURAL JOIN보다 INNER JOIN으로 ON 조건을 걸어주는 게 좋다.


### CROSS JOIN
> 한 테이블의 하나의 row와 다른 테이블의 모든 row를 매칭한다. row끼리의 모든 조합을 보여줌

```sql
SELECT * FROM 테이블1 CROSS JOIN 테이블2
```


### SELF JOIN
> 테이블이 자기 자신과 조인

> 한 테이블 안에서 서로 연관된 정보를 찾기 위해사용


### Non-Equi JOIN
> 등호(=)는 Equi 조인(Equality Condition)

> 그 외의 부등호와 다른 조건은 Non-Equi 조인

---

### 집합 연산
> 테이블을 세로 방향으로 합친다. 

> MySQL에서는 버전 8.0 기준으로 UNION 연산자만 지원하기 때문에 조인을 통해 결과를 얻어야 함.


### UNION(합집합)
> 중복을 제거하고 합친다.

```sql      
SELECT * FROM A
UNION
SELECT * FROM B
```


### UNION ALL
> 중복을 제거하지 않고 겹치는 것을 그대로 보여준다.


### MINUS, EXCEPT(차집합)
```sql
SELECT * FROM A 
MINUS 또는 EXCEPT 
SELECT * FROM B
```


### INTERSECT(교집합)
```sql
SELECT * FROM A
INTERSECT 
SELECT * FROM B
```    

---

### 조인의 기준
> 보통 Foreign Key를 기준으로 하지만, 연관 있는 컬럼을 기준으로 조인을 하기도 한다.


### 테이블 alias
```sql
SELECT
테이블1의 별칭.컬럼,
테이블2의 별칭.컬럼,
...
FROM 테이블1 AS 별칭 RIGHT OUTER JOIN 테이블2 AS 별칭
```
> 테이블에 해당하는 컬럼들도 같은 별칭으로 바꿔줘야 한다.


### ON 대신 USING
> 조인 조건으로 쓰인 컬럼 명이 같으면 USING을 쓸 수 있다.

```sql
FROM 테이블1 INNER JOIN 테이블2 USING(id)
```
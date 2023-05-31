---
title: "MySQL 분석"
layout: post
categories: sql
--- 
 

### NULL
```sql
SELECT * FROM 테이블 WHERE 컬럼 명 IS NULL 또는 IS NOT NULL
```

> IS NULL과 = NULL은 다르다.

> NULL은 아무런 값이 아니기 때문에 어떤 값과 비교할 수 없다.

> NULL에 어떠한 연산을 해도 NULL

> AVG를 통해 평균을 구할 때 NULL을 제외하고 평균값을 구해준다.

### NULL 값 변환
```sql
SELECT COALESCE(컬럼 명, 변환할 값)
```
> NULL이 아닌 값이면 그대로 컬럼값으로, NULL이면 변환 값으로 리턴

---

### CASE
> 조건에 해당하는 컬럼의 값으로 새로운 컬럼을 생성

> 조건을 걸 때, a > 1 and a < 4를 1 < a < 4와 같이 쓰면 안 된다.

```sql
SELECT ...,

CASE 
    WHEN 조건 THEN 값
    WHEN 조건 THEN 값
    ELSE
        값        
END

FROM 테이블
```

```sql
SELECT amount,
(CASE
    WHEN amount < 1 THEN 1
    WHEN amount < 2 THEN 2
    ELSE 3
END) AS "order"
FROM payment
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/06969d30-d692-4308-9aea-3e6737732a22)

---

### CONCAT
> 여러 컬럼이나 문자열을 하나의 컬럼으로 만든다.

```sql
SELECT CONCAT(컬럼 명 1, 컬럼 명 2) FROM 테이블 
```

```sql
SELECT CONCAT(last_name, " ", first_name) AS 'name' FROM actor
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/78b5990b-11c4-4e5c-846b-ef5828dc2d93)
-> ![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/e82213e2-4a80-4a2c-9480-21bc4cc0aabb)


### DISTINCT
> 고윳값만 추출

```sql
SELECT DISTINCT(컬럼 명) FROM 테이블
```


### SUBSTRING
> 문자열 일부를 추출

```sql
SELECT SUBSTRING(컬럼 명, 시작 문자열 위치, 추출 개수) FROM 테이블
```


### LPAD, RPAD
> 문자열의 왼쪽 또는 오른쪽을 특정 문자열로 채움

> 컬럼이 INT형 일 때, 문자열을 넣어주면 자동으로 컬럼 값이 문자열로 형 변환이 된다.

```sql
LPAD(컬럼 명, 컬럼의 총 자릿수, 채울 문자열) 

SELECT LPAD('AA', 5, 'B') 
>>> BBBAA
```
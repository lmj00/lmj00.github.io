---
title: "MySQL JOIN"
layout: post
categories: sql
--- 
 

### JOIN
여러 테이블 합쳐서 하나의 테이블로 보이게 해준다.

  - ### 결합 연산
    테이블을 가로 방향으로 합친다.

    - ### OUTER JOIN

      - ### LEFT OUTER JOIN
        ```sql
        SELECT 
            테이블1.컬럼,
            테이블2.컬럼,
            ...
        FROM 테이블1 LEFT OUTER JOIN 테이블2
        ON 테이블1.id = 테이블2.id
        ```
        
        - 테이블1에 테이블2를 ON 조건으로 합친다.
        - 조건은 서로 값이 같은 로우끼리 연결
        - 컬럼의 값이 NULL인 경우, 테이블2에 존재하지 않는 로우

      <br>    

      - ### RIGHT OUTER JOIN 
        - LEFT OUTER JOIN과 반대
        - 테이블2에 테이블1을 ON 조건으로 합친다.
      
      <br>

    - ### INNER JOIN
      - 두 테이블 조건에 일치하는 컬럼 값이 있는 로우들만 합친다. 
      - 기준 컬럼이 NULL이 되는 경우는 없다.
      - OUTER JOIN과 다르게 기준이 되는 테이블이 없다.

  <br>

  - ### 집합 연산
    테이블을 세로 방향으로 합친다. <br>
    MySQL에서는 버전 8.0 기준으로 UNION 연산자만 지원
    
    - ### UNION(합집합)
      중복을 제거하고 합친다.

      ```sql
      SELECT * FROM A
      UNION
      SELECT * FROM B
      ```
      - ### UNION ALL
        중복을 제거하지 않고 겹치는 것을 그대로 보여준다.

    <br>

    - ### MINUS, EXCEPT(차집합)
      ```sql
      SELECT * FROM A 
      MINUS 또는 EXCEPT 
      SELECT * FROM B
      ```

    - ### INTERSECT(교집합)
      ```sql
      SELECT * FROM A
      INTERSECT 
      SELECT * FROM B
      ```    
    
<br>

### 조인의 기준
- 보통 Foreign Key를 기준으로 하지만, 연관 있는 컬럼을 기준으로 조인을 하기도 한다.


### 테이블 alias
```sql
SELECT
    테이블1의 별칭.컬럼,
    테이블2의 별칭.컬럼,
    ...
FROM 테이블1 AS 별칭 RIGHT OUTER JOIN 테이블2 AS 별칭
```
테이블에 해당하는 컬럼들도 같은 별칭으로 바꿔줘야 한다.


### ON 대신 USING
조인 조건으로 쓰인 컬럼 명이 같으면 USING을 쓸 수 있다.
```sql
FROM 테이블1 INNER JOIN 테이블2 USING(id)
```
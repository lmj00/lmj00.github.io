---
title: "MySQL GROUPING"
layout: post
categories: sql
--- 
 

### GROUP BY
로우들을 여러 개 그룹으로 나눈다.

```sql
SELECT * FROM 테이블 GROUP BY 컬럼 명
```
- 모든 로우가 컬럼을 기준으로 그룹을 가지게 된다.
- DISTINCT와 결괏값이 같은 경우가 있는데, DISTINCT는 컬럼의 고윳값을 추출하고 GROUP BY는 보이는 컬럼 값 안에 해당하는 로우들이 들어있다.


    - ### HAVING
    생성된 그룹에서 특정 그룹만 필터링해서 보여준다.
    ```sql 
    GROUP BY 컬럼 명 HAVING 조건
    ```
        - GROUPING에 사용하지 않은 컬럼을 SELECT 하면 에러가 난다.
        - 대신 집계 함수는 사용할 수 있다. 집계 함수는 특정 로우를 보여주는 게 아니고, 그룹 내의
        &nbsp; 로우 연산을 하기 때문이다.


    - ### WITH ROLLUP
    세부 그룹들을 큰 그룹으로 합쳐줌
    ```sql
    GROUP BY 컬럼 명 WITH ROLLUP 
    ```
      - ### 주의할 점
      GROUP BY 기준들의 순서에 따라 WITH ROLLUP의 결과도 달라진다.


      - ### GROUPING
      실제 NULL을 나타내는 건지, 부분 총계를 나타내기 위한 NULL인지 구분하게 해준다.
 
        ```sql
        GROUPING(컬럼), ...
        ```
        - 실제 NULL을 나타내면 0, 부분 총계로 쓰이던 NULL이면 1로 출력된다.


### SELECT 문 실행 순서
적을 때
> SELECT - FROM - WHERE - GROUP BY - HAVING - ORDER BY - LIMIT

실제 흐름
> FROM - WHERE - GROUP BY - HAVING - SELECT - ORDER BY - LIMIT
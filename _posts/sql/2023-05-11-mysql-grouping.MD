---
title: "MySQL GROUPING"
layout: post
categories: sql
modifited_date: 2023-06-02
--- 
 

### GROUP BY
> 로우들을 여러 개 그룹으로 나눈다.

```sql
SELECT * FROM 테이블 GROUP BY 컬럼 명
```
```sql
SELECT first_name, COUNT(*) AS count 
FROM actor 
GROUP BY first_name
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/f4380aeb-da65-4fb0-bb81-2eae33e099f6)

> 모든 로우가 컬럼을 기준으로 그룹을 가지게 된다.

> DISTINCT와 결괏값이 같은 경우가 있는데, DISTINCT는 컬럼의 고윳값을 추출하고, <br> 
> GROUP BY는 보이는 컬럼 값 안에 해당하는 로우들이 들어있다.


### HAVING
> 생성된 그룹에서 특정 그룹만 필터링해서 보여준다.

```sql 
GROUP BY 컬럼 명 HAVING 조건
```
```sql
SELECT first_name, COUNT(*) AS count 
FROM actor 
GROUP BY first_name
HAVING COUNT(first_name) > 3
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/e23a5708-75d3-4d90-bdfb-f520807434b9)

> GROUPING에 사용하지 않은 컬럼을 SELECT 하면 에러가 난다.

> 대신 집계 함수는 사용할 수 있다. 집계 함수는 특정 로우를 보여주는 게 아니고, 그룹 내의 로우 연산을 하기 때문이다.


### WITH ROLLUP
> 세부 그룹들을 큰 그룹으로 합쳐줌

```sql
SELECT address, gender, COUNT(*)
FROM test2
GROUP BY address, gender WITH ROLLUP
ORDER BY address DESC
``` 
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/3dafb28a-9bfd-4fa4-96e0-1be7eea3ad55)
> 연두색 부분이 부분 총계의 결과

> 파란색 부분은 기준을 정하지 않은 결과 - 전체 총계(총 row 수)

> GROUP BY 뒤에 나오는 그루핑의 순서에 맞춰 부분 총계를 보여줌

> address가 gender보다 상위 컬럼이기 때문에 이것을 기준으로 롤업을 한다.

<br>

```sql
SELECT gender, address, COUNT(*)
FROM test2
GROUP BY gender, address WITH ROLLUP
ORDER BY gender DESC
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/962d5d92-ddf1-4a21-a5e0-aa4e61fd438e)

> GROUP BY 기준들의 순서에 따라 WITH ROLLUP의 결과도 달라진다.


### GROUPING
> WITH ROLLUP을 사용할 때, 실제 NULL을 나타내는 건지, 부분 총계를 나타내기 위한 NULL인지 구분하게 해준다.

> 실제 NULL을 나타내면 0, 부분 총계로 쓰이던 NULL이면 1로 출력된다.

```sql
SELECT address, gender, 
GROUPING(address), GROUPING(gender), COUNT(*) 
FROM test2
GROUP BY address, gender WITH ROLLUP
ORDER BY address DESC
```
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/f44e9083-6412-4afd-99c9-a891922a28c4)


### SELECT 문 실행 순서
적을 때
> SELECT - FROM - WHERE - GROUP BY - HAVING - ORDER BY - LIMIT

실제 흐름
> FROM - WHERE - GROUP BY - HAVING - SELECT - ORDER BY - LIMIT
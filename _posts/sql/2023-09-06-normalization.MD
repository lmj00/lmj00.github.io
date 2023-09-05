---
title: "정규화"
layout: post
categories: sql
---  

### 이상 현상
> 데이터베이스에서 삽입, 갱신, 삭제를 제대로 할 수 없는 경우

> 데이터 모델링을 제대로 하지 않았을 때 발생


### [정규화](https://www.javatpoint.com/dbms-normalization)
> 데이터의 중복을 최소화하고 데이터 일관성을 유지하기 위한 중요한 프로세스

> 이상 현상을 제거하는 데 필요

> 여러 가지 정규화가 있지만, 제3 정규형에 만족하면 정규화가 잘 된 데이터베이스

> 데이터 모델을 만들고, 실제 데이터베이스에 반영하기 전에 적용하는 것이 좋다. 

---

### 1NF - 제1 정규형
> 각 컬럼은 더 이상 분해할 수 없는 최소한의 데이터 단위여야 한다.

##### 1NF를 만족하지 않는 테이블
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/3e89c5b3-a473-4c94-89fe-6591936fb77a)
> price, balance 컬럼의 값이 원자적이지 않다.

<br>

##### 1NF를 만족하는 테이블
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/476d67dd-ab53-4c00-b826-93016a542e6c)

---

### 함수 종속성
> 테이블 안의 attribute들 사이에서 생기는 관계

> x컬럼의 값에 따라 y컬럼의 값이 결정될 때, y는 x에 함수 종속성이 있다고 표현 (x -> y)

> 하나의 컬럼 값으로 다른 컬럼의 값이 결정되는 것

> 한 테이블에 여러 개의 함수 종속성이 있을 수도 있다.


### 이행적 함수 종속성
> x -> y, y-> z 일 때, x -> z를 만족시키는 것을 의미한다.


### Candidate Key(후보키)
> 하나의 로우를 특정지을 수 있는 attribute들의 최소 집합

> 여러 개의 후보키가 있을 수 있지만, 하나의 pk만 있을 수 있다.

> Candidate Key에 포함되는 속성들을 `prime attribute`

> Candidate Key의 일부가 아닌 모든 속성은 `none-prime attribute`


### 2NF - 제 2정규형
> 1NF를 만족해야 한다.

> 후보키의 일부에 대해서만 종속되는 `non-prime attribute`가 없어야 한다. (부분 함수 종속성)

<br>

##### 2NF를 만족하지 않는 테이블
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/3626e63f-6b27-4f01-9250-66d8d35e0a0b)
> coin_name은 price와 balance에 종속되어 있고, user_id에 종속되어 있지 않다.

> price와 balance는 user_id와 무관하게 coin_name에 의해 결정되므로 부분 함수 종속성

<br>

##### 2NF를 만족하는 테이블
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/6357f69d-a4c1-43f4-93a1-d004accda514)


---

### 3NF - 제 3정규형
> 2NF를 만족해야 한다.

> 테이블 안에 있는 모든 attribute들은 pk에 대해서만 함수 종속성이 있어야 한다. <br> (이행적 함수 종속성을 제거해야 한다)


### 비정규화
> 성능 개선을 위해 정규형에 부합하는 테이블을 정규형을 지키지 않게 바꿈

> 정규화된 데이터베이스에서 원하는 데이터를 찾기 위해 조인을 통해서 테이블 합쳐야 하는 경우가 많다. 이러한 조인을 회피하여 쿼리 성능 개선

> 읽기(READ) 연산이 많은 경우에 사용
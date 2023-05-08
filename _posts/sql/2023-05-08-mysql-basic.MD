---
title: "MySQL 기본"
layout: post
categories: sql
--- 


## 조건 표현식
  - 같지 않음은 != 또는 <>
  - BETWEEN A AND B - (A 이상 B 이하)

  - #### 일치하는 값이 있는 IN
    - SELECT * FROM member where age IN(20, 30);
    - 20세와 30세만 조회

  - #### LIKE
    - 컬럼명 LIKE '%A' - 문자열의 마지막 부분이 A로 끝나는 단어의 문자열을 가져온다.
    - 'A%' - 문자열의 첫 부분이 A인 단어로 시작하는 문자열을 가져온다.
    - '%A%' - A가 포함된 모든 문자열
    - LIKE에서 _는 한 글자를 나타낸다.

- #### 여러 조건에서 먼저 실행되길 원하는 조건은 괄호로 씌워주는 습관을 길러라
    - 괄호가 연산자 순위가 가장 높기 때문


## DATE 타입 
- #### YEAR, MONTH, DAY
    - SELECT * FROM member WHERE YEAR(birthday) = '2000'

- #### 날짜 간의 차이
    - SELECT DATEDIFF(날짜 1, 날짜 2)  

- #### 날짜 더하기 빼기
    - DATE_ADD(날짜, INTERVAL 1 DAY)
    - DATE_SUB(날짜, INTERVAL 60 MINUTE)

- #### UNIX Timestamp 
    - UNIX_TIMESTAMP(날짜)


## 테이블을 지정 
- 다른 DB에서 같은 이름의 테이블이 있을 수도 있으니, 테이블을 지정해주는 게 좋다.
  - SELECT * FROM DB 이름.테이블; <br> 또는
  - USE {DB 이름}; <br>
  SELECT * FROM 테이블


## Escape
- `% ' _ "`와 같은 문자들은 표현식에 포함되는 문자들이다.
- 표현식이 아닌 문자로 표현하려면 해당 문자 앞에 \를 붙여준다.


## 대소문자 구분
- LIKE BINARY '%A%' 
- BINARY를 붙이면 0과 1로 이루어진 문자열을 정확히 비교하기 때문에 소문자와 대문자를 구별


## CAST
- 특정 데이터 타입의 데이터를 일시적으로 다른 데이터 타입으로 변경할 수 있게 해주는 함수
- CAST(데이터 AS 바꿀 데이터 타입)
- `signed`: 양수와 음수를 포함한 모든 정수를 나타낼 수 있는 데이터 타입


## LIMIT
- 현재 조회된 ROW 중에서 몇 개만 추려서 보여준다.
- LIMIT (개수)
- LIMIT (시작 ROW, 개수)
- ROW는 0번째부터 시작
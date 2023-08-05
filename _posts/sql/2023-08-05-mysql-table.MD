---
title: "MySQL Table"
layout: post
categories: sql
---  


### [컬럼 데이터 타입](https://dev.mysql.com/doc/refman/8.0/en/data-types.html)
> 숫자형

| Type      | Bytes | Signed                                     | Unsigned                 |
|-----------|-------|--------------------------------------------|--------------------------|
| TINYINT   | 1     | -128 ~ 127                                 | 0 ~ 255                  |
| SMALLINT  | 2     | -32768 ~ 32767                             | 0 ~ 65535                |
| MEDIUMINT | 3     | -8388608 ~ 8388607                         | 0 ~ 16777215             |
| INT       | 4     | -2147483648 ~ 2147483647                   | 0 ~ 4294967295           |
| BIGINT    | 8     | -9223372036854775808 ~ 9223372036854775807 | 0 ~ 18446744073709551615 |

> 실수형

- 고정 소수점
  - DECIMAL(M, D)
  - M: 총 자릿수, D: 소수점 뒤 자릿수
  - DECIMAL(5, 2) => -999.99 ~ 999.99

- 부동 소수점

| Type   	| Bytes 	| 범위                                                                                                   	|
|--------	|-------	|--------------------------------------------------------------------------------------------------------	|
| FLOAT  	| 4     	| -3.4028235E+38 ~ -1.17549435E-38, 1.17549435E-38 ~ 3.4028235E+38                                       	|
| DOUBLE 	| 8     	| -1.7976931348623157E+308 ~ -2.2250738585072014E-308, 2.2250738585072014E-308 ~ 1.7976931348623157E+308 	|

> 날짜 및 시간

| Type      | 값                       |
|-----------|--------------------------|
| DATE      | YYYY-MM-DD               |
| DATETIME  | YYYY-MM-DD hh:mm:ss      |
| TIME      | hh:mm:ss                 |
| TIMESTAMP | YYYY-MM-DD hh:mm:ss UTC  |
| YEAR      | YYYY                     |


> 문자열

| Type    	| 길이       	| 참고                                 	|
|---------	|------------	|--------------------------------------	|
| CHAR    	| 0 ~ 255    	| 고정 길이                            	|
| VARCHAR 	| 0 ~ 65,535 	| 가변 길이                            	|
| TEXT    	| 0 ~ 65,535 	| TINYTEXT, TEXT, MEDIUMTEXT, LONGTEXT  |

---

### 물리 삭제
> row를 삭제

```sql
DELETE FROM actor WHERE id = 1;
```

### 논리 삭제
> 삭제를 나타내는 컬럼을 생성 후, 삭제가 되었다는 값을 기입

```sql
UPDATE actor SET is_deleted = 1 WHERE id = 1;
```

---

### 컬럼 추가
```sql
ALTER TABLE `테이블 이름` ADD `컬럼 이름` `데이터 타입` `속성`;
```


### 컬럼 이름 변경
```sql
ALTER TABLE `테이블 이름` RENAME COLUMN `기존 컬럼 이름` TO `새로운 컬럼 이름`; 
```


### 컬럼 삭제
```sql
ALTER TABLE `테이블 이름` DROP COLUMN `삭제할 컬럼 이름`;
```


### 컬럼 데이터 타입 변경
```sql
ALTER TABLE `테이블 이름` MODIFY `컬럼 이름` `데이터 타입`;
```

> 현재 컬럼의 값이 변경할 데이터 타입과 다를 경우, 컬럼의 값을 바꿀 데이터 타입으로 먼저 바꾸고 나서, 컬럼의 데이터 타입을 변경해야 한다.


### 컬럼 속성 변경
```sql
ALTER TABLE `테이블 이름` MODIFY `컬럼 이름` `데이터 타입` `속성`;
```
- 컬럼 속성 변경 시, 원래 데이터 타입도 써줘야 한다.
- 데이터 타입과 컬럼 속성을 동시에 변경할 수도 있다.


### 컬럼 DEFAULT 설정
```sql
ALTER TABLE `테이블 이름` MODIFY `컬럼 이름` `데이터 타입` `속성` DEFAULT `설정할 값`;
```


### 컬럼에 현재 시간 넣기

#### [NOW()](https://dev.mysql.com/doc/refman/8.0/en/date-and-time-functions.html#function_now) 
```sql
INSERT INTO employees (created_at) VALUES (NOW());
```

<br>

#### DATETIME, TIMESTAMP 타입의 컬럼에서 사용할 수 있는 속성
`DEFAULT CURRENT_TIMESTAMP`
> 새 row가 추가 될 때, 해당 컬럼의 값을 현재 시각으로 설정

```sql
CREATE TABLE my_table (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    content VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

결과
```sql
INSERT INTO my_table (content) VALUES ('test');
``` 
![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/a5518168-8e9e-44c3-a95c-16ee9178e65e)

<br>

`ON UPDATE CURRENT_TIMESTAMP`
> 해당 컬럼이 업데이트되면, 현재 시각으로 갱신되게 설정

```sql
CREATE TABLE my_table (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    content VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

결과
```sql
INSERT INTO my_table (content) VALUES ('test');

UPDATE my_table SET content = 'test2' WHERE id = 1;
```

![image](https://github.com/lmj00/lmj00.github.io/assets/54443194/3490f365-e2d5-411a-b678-23aa913efccc)


### 컬럼 UNIQUE
```sql
ALTER TABLE `테이블 이름` MODIFY `컬럼` `데이터 타입` `속성` UNIQUE;
```


### 컬럼을 테이블의 첫 번째 위치로 옮기기
```sql
ALTER TABLE `테이블 이름` MODIFY `컬럼` `데이터 타입` `속성` FIRST;
```


### 컬럼 순서 바꾸기
```sql
ALTER TABLE `테이블 이름` MODIFY `컬럼` `데이터 타입` `속성` AFTER `컬럼`;
```


### 컬럼 이름과 컬럼 데이터 타입, 속성을 동시에 수정하기
```sql
ALTER TABLE `테이블 이름` CHANGE `기존 컬럼` `바꿀 컬럼` `데이터 타입` `속성`;
```


### 여러 작업 동시에 수행
```sql
ALTER TABLE `테이블 이름`
    CHANGE ...,
    DROP COLUMN ...,
    ADD ...;
```

---

### 테이블 CONSTRAINT
> 무결성을 유지하고 데이터의 일관성을 보장하기 위해 사용되는 조건

```sql
ALTER TABLE `테이블 이름` ADD CONSTRAINT `제약 조건 이름` CHECK `조건`;
```


### 제약 조건 삭제
```sql
ALTER TABLE `테이블 이름` DROP CONSTRAINT `제약 조건 이름`;
```


### 테이블 이름 변경
```sql
RENAME TABLE `현재 테이블 이름` TO `바꿀 테이블 이름`;
```


### 테이블 복사
```sql
CREATE TABLE `테이블 이름` AS SELECT * FROM `복사할 테이블 이름`;
```


### 테이블 컬럼, 데이터 타입, 제약 조건 등을 복사
```sql
CREATE TABLE `테이블 이름` LIKE `복사할 테이블 이름`;
```


### 다른 테이블 로우를 복사하기
```sql
CREATE TABLE `테이블 이름` LIKE `복사할 테이블 이름`;

INSERT INTO `테이블 이름` SELECT * FROM `복사할 테이블 이름`;
```
> 두 테이블의 컬럼 구조가 같아야 한다.


### TRUNCATE
> 테이블 데이터 전체 삭제

```sql
TRUNCATE TABLE `테이블 이름`;
```
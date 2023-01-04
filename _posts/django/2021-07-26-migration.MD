---
title: "Migration"
layout: post
categories: django
modified_date: 2022-10-24
---

## migration
```terminal
$ python manage.py makemigrations
```
- django의 데이터베이스 변경 사항에 대한 버전 컨트롤 시스템
- Model을 생성하거나 변경했을 때 migration을 하나씩 만드는 것
- models.py의 내용을 확인 후 migrations 폴더 안에 .py파일로 기록
- App 단위로 관리
![image](https://user-images.githubusercontent.com/54443194/197414829-fee41252-c5c0-40de-9338-8e6f7f2f2d3b.png)


## migrate
```terminal
$ python manage.py migrate
```	
- 만든 migration을 실제 데이터베이스에 적용하는 것
- ORM이 migration 폴더 안에 있는 .py 파일을 확인 후, SQL로 변환하여 실행


## migrations 파일 이름 설정
```terminal
$ python manage.py makemigrations --name {파일 이름}
```
![image](https://user-images.githubusercontent.com/54443194/197416777-23e89cf8-311d-4646-b6e0-da9504aa5922.png)
- 가끔 xxxx_auto.py와 같이 생성되기 때문에 변경된 흐름을 알 수 있도록 이름을 정해주는 게 좋다.


### 이전 migration으로 되돌리기
```terminal
$ python manage.py migrate {앱 이름}{migration 번호}
```


### 생성되어 있는 migration 목록 보기 
```terminal
$ python manage.py showmigrations
```
- [X]로 되어 있는 부분은 이미 django에 반영이 된 것
- 특정 앱만 보고 싶으면 뒤에 {앱 이름}


### ORM을 통해서 변환된 SQL 보기
```terminal
$ python manage.py sqlmigrate {앱 이름}{migration 번호}
```



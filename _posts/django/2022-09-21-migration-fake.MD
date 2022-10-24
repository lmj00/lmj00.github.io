---
title: "[Django] migration fake"
layout: post
categories: Django
--- 
  

## 문제
migrate를 했음에도 `No migrations to apply.`가 뜨고 테이블이 생기지 않았다. <br>
init.py 파일을 제외하고 migration, migrate를 실행해도 생기지 않았다.


## 원인
예전 model로 만들어진 테이블이 이미 있는 경우 생기는 문제 같다.


## 해결 방법
```terminal
$ python manage.py migrate --fake APPNAME zero
```
[stackoverflow](https://stackoverflow.com/questions/25958708/django-1-7-no-migrations-to-apply-when-run-migrate-after-makemigrations]) <br>
[django-docs](https://docs.djangoproject.com/en/3.2/ref/django-admin/#cmdoption-migrate-fake-initial)


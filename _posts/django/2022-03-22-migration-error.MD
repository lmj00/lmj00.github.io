---
title: "[Django] migration 오류"
layout: post
categories: Django
--- 


app 구조를 변경하다가 migate 과정에서 오류가 발생했다.

```terminal 
$ find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
```
```terminal
$ find . -path "*/migrations/*.pyc" -delete
```
이후 dbsqlite3 삭제

`이전의 앱 파일이나 프로젝트의 설정을 그대로 가져오면 오류가 나기 때문에 migrate가 진행된 후 적용시켜야 한다.`





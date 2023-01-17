---
title: "HttpRequest objects"
layout: post
categories: django
--- 


## [HttpRequest objects](https://docs.djangoproject.com/en/4.0/ref/request-response/#httprequest-objects)
- 여러가지가 있는데 사용한 것만 기록


### HttpRequest.method
```python
if request.method == 'GET':
    do_something()
elif request.method == 'POST':
    do_something_else()
```
- GET, POST는 대문자로


### HttpRequest.META
```python
HttpRequest.META['HTTP_REFERER']
```
- HTTP_REFERER: 참조 페이지


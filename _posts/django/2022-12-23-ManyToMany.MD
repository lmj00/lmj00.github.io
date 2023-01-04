---
title: "Many-To-Many Field"
layout: post
categories: django
--- 

## [Many-to-Many Field](https://docs.djangoproject.com/en/3.2/ref/models/fields/#manytomanyfield)
- 일대일 관계와 달리 두 모델 중 아무거나 선택해도 상관없다.
- 참조하는 오브젝트가 여러 개이기 때문에 on_delete 옵션이 없다.


## [Argument](https://docs.djangoproject.com/en/3.2/ref/models/fields/#manytomany-arguments)

> ManyToManyField.symmetrical

```python
from django.db import models

class Person(models.Model):
    friends = models.ManyToManyField("self", symmetrical="False")
```
- 다대다 관계는 A와 B, B와 A가 서로 대칭관계이다.
- 대칭관계를 원하지 않는다면 symmetrical를 False로 하여 비대칭 관계로 만든다.


## self를 쓰는 이유?
- User로 예를 들면, 유저 A는 다른 유저들을 팔로우할 수 있고, 다른 유저들도 A를 팔로우할 수 있다.<br>
user끼리 참조하기 때문에 사용한다.
- 일대일, 외래키도 사용 가능하다.

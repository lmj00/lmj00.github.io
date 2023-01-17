---
title: "get_or_create"
layout: post
categories: django
--- 


## [get_or_create()](https://docs.djangoproject.com/en/3.2/ref/models/querysets/#get-or-create)
```python
obj, created = Person.objects.get_or_create(
    first_name='John',
    last_name='Lennon',
    defaults={'birthday': date(1940, 10, 9)},
)
```

- 조건에 맞는 오브젝트가 있으면 obj 저장, created는 bool로 튜플 반환 `(obj, created)`
- [update_or_create()](https://docs.djangoproject.com/en/3.2/ref/models/querysets/#update-or-create)도 있다.
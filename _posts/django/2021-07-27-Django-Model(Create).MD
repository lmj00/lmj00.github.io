---
title: "[Django] Model (Create)"
layout: post
categories: Django
---

### shell 진입
```terminal
python manage.py shell
```


### model 불러오기
```python
from {app}.models import {class}
```


### 데이터베이스에 데이터 저장하기
```python
{model}.objects.create({값})
```
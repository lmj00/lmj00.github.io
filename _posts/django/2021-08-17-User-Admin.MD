---
title: "User Admin" 
layout: post
categories: django
---

## Admin 등록
```python
from django.contrib import admin 
from django.contrib.auth.admin import UserAdmin
from .models import User 

admin.site.resigster(User, UserAdmin) 
```
`UserAdmin은 User모델에 대해 인터페이스 제공`

 
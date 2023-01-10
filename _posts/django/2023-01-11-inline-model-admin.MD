---
title: "InlineModelAdmin"
layout: post
categories: django
--- 


## [InlineModelAdmin](https://docs.djangoproject.com/en/3.2/ref/contrib/admin/#inlinemodeladmin-objects)

- 어드민 사이트에서 모델과 상위 모델을 같은 페이지에서 편집할 수 있는 기능을 inline이라고 한다.


```python
from django.db import models

class Author(models.Model):
   name = models.CharField(max_length=100)

class Book(models.Model):
   author = models.ForeignKey(Author, on_delete=models.CASCADE)
   title = models.CharField(max_length=100)
```
```python
from django.contrib import admin

class BookInline(admin.TabularInline): 
    model = Book

class AuthorAdmin(admin.ModelAdmin):
    inlines = [
        BookInline,
    ]	
    # AuthorAdmin에서 BookInLine 사용
admin.site.register(Author, AuthorAdmin)
```


InlineModelAdmin은 두 가지 하위 클래스를 제공하는데, 차이점은 렌더링 된 템플릿의 모습
- TabularInline
- StackedInline


### [GenericForiegnKey로 관계를 형성했을 때](https://docs.djangoproject.com/en/3.2/ref/contrib/admin/#using-generic-relations-as-an-inline)
- GenericStackedInline 또는 GenericTabularInline을 사용해야 한다.


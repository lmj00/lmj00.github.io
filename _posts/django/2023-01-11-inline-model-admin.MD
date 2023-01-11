---
title: "InlineModelAdmin"
layout: post
categories: django
modified_date: 2023-01-12
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

```


InlineModelAdmin은 두 가지 하위 클래스를 제공하는데, 차이점은 렌더링 된 템플릿의 모습
- TabularInline
- StackedInline


### [GenericForiegnKey로 관계를 형성했을 때](https://docs.djangoproject.com/en/3.2/ref/contrib/admin/#using-generic-relations-as-an-inline)
- GenericStackedInline 또는 GenericTabularInline을 사용해야 한다.


### [다대다 관계로 형성했을 때](https://docs.djangoproject.com/en/3.2/ref/contrib/admin/#working-with-many-to-many-models)
```python
from django.db import models

class Person(models.Model):
    name = models.CharField(max_length=128)

class Group(models.Model):
    name = models.CharField(max_length=128)
    members = models.ManyToManyField(Person, related_name='groups')
```
```python
from django.contrib import admin

class MembershipInline(admin.TabularInline):
    model = Group.members.through

class PersonAdmin(admin.ModelAdmin):
    inlines = [
        MembershipInline,
    ]

class GroupAdmin(admin.ModelAdmin):
    inlines = [
        MembershipInline,
    ]
    exclude = ('members',)

admin.site.register(Person, PersonAdmin)
admin.site.register(Group, GroupAdmin)
```

### exclude
- 


### [fk_name](https://docs.djangoproject.com/en/3.2/ref/contrib/admin/#working-with-a-model-with-two-or-more-foreign-keys-to-the-same-parent-model)을 정의해야 할 때
- 동일한 모델을 가리키는 외래 키가 두 개 이상 있을 때
- self 관계일 때


### UserAdmin 클래스에 inlines 추가하기
```python
UserAdmin.inlines = (inline 클래스,) 
```
`튜플 형식에서 요소가 하나만 있을 경우에는 ,를 꼭 붙여야 한다.`

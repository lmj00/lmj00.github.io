---
title: "Contenttypes"
layout: post
categories: django
modified_date: 2023-01-17
--- 

## [Contenttypes](https://docs.djangoproject.com/en/2.2/ref/contrib/contenttypes/)

- 하나의 모델을 여러 모델과 연결할 수 있다. 
- 중복으로 관계를 맺는 모델이 있을 때 사용


## [Generic relations](https://docs.djangoproject.com/en/2.2/ref/contrib/contenttypes/#generic-relations-1)

```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

class TaggedItem(models.Model):
    tag = models.SlugField()

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE) # 1
    object_id = models.PositiveIntegerField() # 2 
    content_object = GenericForeignKey('content_type', 'object_id') # 3

    def __str__(self):
        return self.tag
```


`# 3 - GenericForeignKey에 들어가는 파라미터들을 'content_type', 'object_id'로 정의하면`<br>
`아래와 같이 생략할 수 있다.`

```python
content_object = GenericForeignKey() # 3
```


### Content type id 템플릿으로 전달
```python
# views.py
from django.contrib.contenttypes.models import ContentType

def get_context_data(self, **kwargs):
    ... 
    ContentType.objects.get(model='모델명')
	
    return context
```



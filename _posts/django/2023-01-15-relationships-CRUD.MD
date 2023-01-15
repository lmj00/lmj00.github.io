---
title: "관계 CRUD"
layout: post
categories: django
--- 


## ForeignKey, OneToOneField CREATE
- object를 넘겨도 되고, object id를 넘겨도 된다.`(object_id = 1)`


## GenericForeignKey CREATE
- content_type, id로 전달하거나, content_object로 전달
- content_object로 전달할 때 id만 넘겨주면 ContentType을 파악할 수 없어 오류가 발생하니 오브젝트를 넘겨줘야한다.


## ManyToManyField CREATE, DELETE
```python
object.field.add()
object.field.remove()
```
- object나 object_id로 전달
- 없는 파라미터는 전달되어도 무시
- 역관계에서도 가능


## UPDATE
```python
obejct.field = value
object.save()
```
- 
값을 수정후 save()
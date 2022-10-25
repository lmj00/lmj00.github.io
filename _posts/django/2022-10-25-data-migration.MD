---
title: "[Django] Data Migrations"
layout: post
categories: Django
--- 

## [Data Migrations](https://docs.djangoproject.com/en/4.1/topics/migrations/#data-migrations)
- 새로운 컬럼을 만들 때 데이터도 넣어준다.
- 테이블 여러 개 나누거나 합칠 때도 사용.


## 방법
비어있는 마이그레이션 파일을 만든다.

```terminal
$ python manage.py makemigrations --empty yourappname
```
```python
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('yourappname', '0001_initial'),
    ]

    operations = [
    ]
```
<br>

마이그레이션 함수는 apps과 schema_editor를 파라미터로 받는다. 
```python
from django.db import migrations

def combine_names(apps, schema_editor):
    # We can't import the Person model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    Person = apps.get_model('yourappname', 'Person') # 모델은 이 형식으로 가져와야 함.
    for person in Person.objects.all():
        person.name = '%s %s' % (person.first_name, person.last_name)
        person.save()

class Migration(migrations.Migration):

    dependencies = [
        ('yourappname', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(combine_names),
    ]
```
이후 migrate를 하면 data migration이 적용된다.


## 되돌리기
아무런 작업을 하지 않길 원하면 RunPython.noop 메서드를 전달
```python
operations = [
	migrations.RunPython(comb, migrations.RunPython.noop)
]
```

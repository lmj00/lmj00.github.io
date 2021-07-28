---
title: "[Django] Migration"
layout: post
---

### migration
- django의 데이터베이스 변경 사항에 대한 버전 컨트롤 시스템
- Model을 생성하거나 변경했을 때 migration을 하나씩 만드는 것

```python
python manage.py makemigrations
```

### migrate
- 만든 migration을 실제 데이터베이스에 적용하는 것

```python
python manage.py migrate
```

이전 migration으로 되돌리기
```python
python manage.py migrate {앱 이름}{migration 번호}
```


### 생성되어 있는 migration 목록 보기 
```pyton
python manage.py showmigrations
```
`[X]로 되어 있는 부분은 이미 django에 반영이 된 것`
- 특정 앱만 보고 싶으면 뒤에 {앱 이름}

### ORM을 통해서 변환된 SQL 보기
```python
python manage.py sqlmigrate {앱 이름}{migration 번호}
```

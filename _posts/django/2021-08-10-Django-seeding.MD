---
title: "[Django] Seeding"
layout: post
categories: Django
---

## 시딩
- 향후 개발하려는 데이터로 데이터베이스를 채우거나, 테스트 하고자 할 때 사용하는 방법  
- seed_file은 JSON, XML 등의 파일형식으로 사용
- 유효성 검증은 거치치 않은 데이터


## seed_file 만들기
1. `내용을 채운다.`
2. `python manage.py dumpdata posts --indent=2 > posts_data.json`
3. `pyhton manage.py loaddata {seed_file}`


## django-seed
- 모델에 정의된 필드를 보고 데이터를 자동으로 생성하는 패키지

1. `pip install django-seed`
2. `setting에 들어가서 INSTALLED_APPS에 'django_seed'`
3. `python manage.py seed posts --number=50(데이터 개수)`
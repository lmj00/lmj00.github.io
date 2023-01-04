---
title: "배포 준비"
layout: post
categories: django
---

1.  디버그 모드 끄기
- 웹 사이트의 민감한 정보가 유출될 가능성이 있음
- settings.py -> debuf = false


2. ALLOWED_HOSTS 
- 해당 사이트가 서비스할 수 있게 함


3. 정적파일 한 곳으로 모으기
- 배포 사이트에선 한 곳에서 찾기 때문
- settings.py 맨 아래에 STATIC_ROOT = os.path.join(BASE_DIR, 'static')


4. 모든 static 파일 복사
- python manage.py collectstatic
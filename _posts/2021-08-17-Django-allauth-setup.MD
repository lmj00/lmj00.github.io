---
title: "[Django] allauth-setup"
layout: post
---

## setup
설치 가이드: [django-allauth installation](https://django-allauth.readthedocs.io/en/latest/installation.html) 
1. pip install django-allauth
2. settings.py에 AUTHENTICATION_BACKENDS  추가
3. settings.py에 INSTALLED_APPS 추가 <br/>
` 소셜 로그인 부분도 필요하면 추가하면 된다` <br/>
4. settings.py에 SITE_ID 추가 <br/>
`django.contrib.sites는 장고 프로젝트 하나로 여러 웹 사이트를 운영할 수 있다.` <br/> 
`따라서 SITE_ID는 사이트 마다의 데이터베이스 ID를 뜻한다.`
5. urls.py에 패턴 추가 <br/>
`path에 경로를 ""(공백)으로 하면 /login, /singup와 같은 경로`


## Email settings
- allauth가 제공하는 이메일 인증, 비밀번호 찾기 활용
- EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
- 현재는 터미널 콘솔로 설정

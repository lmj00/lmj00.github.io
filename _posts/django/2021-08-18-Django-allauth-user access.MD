---
title: "[Django] allauth user access"
layout: post
categories: Django
---

## allauth-redirection
`ACCOUNT_SIGNUP_REDIRECT_URL = 'index'` <br/>
`LOGIN_REDIRECT_URL = 'index'` <br/> 
`ACCOUNT_LOGOUT_ON_GET = True (바로 로그아웃)`


## User 접근
- view에서는 request.user
- template에서는 {{user}}


## 로그인 유무
`request.user.is_authenticated (bool 반환)`


## allauth url name 참조
가장 쉬운 방법은 [urls.py](https://github.com/pennersr/django-allauth/blob/master/allauth/account/urls.py)를 보면 된다. 
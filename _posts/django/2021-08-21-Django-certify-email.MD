---
title: "[Django] 이메일 인증"
layout: post
categories: Django
---

### 이메일 인증
```terminal 
ACCOUNT_EMAIL_VARIFICATION = { }
```
- 세 가지 옵션
1. mandatory = 이메일 인증을 완료할 때 까지 로그인을 할 수 없다.
2. optional(기본 값) = 회원가입 시 인증 요청이 발송되지만, 인증을 하지 않아도 로그인 가능
3. none = 이메일 인증이 필요 없고, 인증 요청 발송이 되지 않는다.


### 링크를 클릭하면 인증완료   
```terminal 
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
```

### urls
```terminal
from django.views.generic import TemplateView

path("email-confirmation-done/",
TemplateView.as_view(template_name="{앱 이름}/email_confirmation_done.html"),
name="account_email_confirmation_done" )
```
`제네릭 뷰에서 템플릿 뷰를 사용하면 된다.` <br/>
`템플릿 뷰의 장점은 뷰를 정의하지 않고 사용 가능 하다.`


### 로그인이 되어 있을 때
```terminal
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL  = {"경로"}
```

### 로그인이 안 되어 있을 때
```terminal
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = {"경로"}
```
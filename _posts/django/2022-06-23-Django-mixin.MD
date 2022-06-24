---
title: "[Django] Mixin"
layout: post
categories: Django
modified_date: 2022-06-25
--- 
  
## Mixin
파이썬에서 사용하는 툴


## django.contrib.auth
접근 제어에 관련된 mixin 패키지가 존재하지만 커스터마이징 어려움


## django-braces
- [Access Mixins](https://django-braces.readthedocs.io/en/latest/access.html) - 접근 제어에 관련
- [Form Mixins](https://django-braces.readthedocs.io/en/latest/form.html) - form이 처리되는 방식을 수정
- [Other Mixins](https://django-braces.readthedocs.io/en/latest/other.html)	 - json, ajax, context 등


---


## LoginRequiredMixin
```python
pip install django-braces
settings에 가서 LOGIN_URL = 'account_login'
-> 로그인이 안 되어있을 때 로그인 페이지로 redirect
```

```python
from django.views.generic import TemplateView
from braces.views import LoginRequiredMixin

class SomeSecretView(LoginRequiredMixin, TemplateView):
    template_name = "path/to/template.html"

    #optional
    login_url = "/signup/"
    redirect_field_name = "hollaback"
    raise_exception = True

    def get(self, request):
        return self.render_to_response({})
```


## 주의
request가 view에 도착하기 전에 mixin 로직을 거치기 때문에 LoginRequiredMixin을 파라미터 <br>
첫 번째 값으로 써야 함.


## 결과
`http://127.0.0.1:8000/login/?next=/posts/new/`<br>
<br> url을 보면 ?next=/ 뒤에 파라미터가 있다. <br>
로그인을 성공하면 next 파라미터의 url로 redirect 됨


---


## UserPassesTestMixin
- 유저가 mixin을 통과하지 못할 때 흐름을 제어

```python
from django.views.generic import TemplateView
from braces.views import UserPassesTestMixin


class SomeUserPassView(UserPassesTestMixin, TemplateView):
        
    ...
    
    redirect_unauthenticated_users = True
    raise_exception = {functions에서 만든 함수}  # 인증 페이지 redirect

    def test_func(self, user):
        return EmailAddress.objects.filter(user=user, verified=True).exists()
``` 


```python
redirect_unauthenticated_users = bool
```
> view 접근이 차단 된 유저를 로그인 유무에 따라 다르게 처리<br>
> True - 로그인이 안 된 유저는 로그인 페이지로 redirect, 로그인 된 유저는 exception<br>
> False - 로그인 유무 상관없이 exception

 
## functions
- redirect할 함수

```python
from django.shortcuts import redirect
from allauth.account.utils import send_email_confirmation

def test(self, request):
    send_email_confirmation(request, request.user)
    return redirect({이메일 인증 요청 url}) 
```
> allauth - send_email_confirmation<br>
> 이메일 인증을 하지 않은 유저는 이메일 인증 발송을 해줌 


> redirect - 프로젝트 url에서 요청 템플릿으로 아래와 같이 리턴 path 지정해줘야 함
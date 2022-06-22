---
title: "[Django] Mixin"
layout: post
categories: Django
--- 
  
## Mixin
파이썬에서 사용하는 툴


## django.contrib.auth
접근 제어에 관련된 mixin 패키지가 존재하지만 커스터마이징 어려움


## django-braces
- [Access Mixins](https://django-braces.readthedocs.io/en/latest/access.html) - 접근 제어에 관련
- [Form Mixins](https://django-braces.readthedocs.io/en/latest/form.html) - form이 처리되는 방식을 수정
- [Other Mixins](https://django-braces.readthedocs.io/en/latest/other.html)	 - json, ajax, context 등


## 사용 방법
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



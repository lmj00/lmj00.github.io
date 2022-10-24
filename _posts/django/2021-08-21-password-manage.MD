---
title: "[Django] 비밀번호 관리"
layout: post
categories: Django
---

### timeout
```terminal
PASSWORD_RESET_TIMEOUT_DAYS = {기간}
```
`기본 값은 3일`


### 웹 사이트에서 비밀번호 변경
```django
{% raw %}{% url 'account_change_password' %}{% endraw %}
```


### 비밀번호 변경 후 redirect 
- view

```python 
from allauth.account.views import PasswordChangeView
from django.urls import reverse

class CustomPasswordChangeView(PasswordChangeView):
    def get_success_url(self):
        return reverse("index")
```

- urls

```python
from {앱 이름}.views import CustomPasswordChangeView

path('password/change/', CustomPasswordChangeView.as_view(), name="account_password_change")
```


---
title: "[Django] nickname"
layout: post
---

## model 정의
```
class User(AbstractUser):
    nickname = models.CharField(max_length=20, unique=True, null=True)
```


## admin
```terminal
UserAdmin.fieldsets += ("Custom fields", {"fields": ("nickname", )})
```
`User 모델의 추가 필드는 어드민 페이지에 나타나지 않기 때문에 추가`


## form
```python
from django import forms
from .models User

class SignupForm(forms.Modelform):
    class Meta:
        model = User
        fields = ["nickname"]
    
    def signup(self, request, user):
        user.nickname = self.cleaned_deta["nickname"] (작성된 폼의 데이터를 가져옴)
        user.save()
```


## settings
```terminal
ACCOUNT_SIGNUP_FORM_CLASS = "{앱 이름}.forms.{폼 클래스}"
```
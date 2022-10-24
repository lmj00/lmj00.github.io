---
title: "[Django] signup validation"
layout: post
---
 

## 유효성 검사 언어
```terminal
LANGUAGE_CODE = "ko"
```

## 오류 메세지 
```python
class User(AbstractUser):
    nickname = models.CharField(
        max_length=15,
        unique=True, 
        null=True,  
        validators=[{사용할 validators}]
        error_messages={'unique': '이미 사용중인 닉네임입니다.'},
     )
```

## 작성한 validator 추가
```python
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "{앱 이름}.validators.{validator class 이름}",
    },
]
```

 
### 폼에 오류가 있어도, 입력했던 비밀번호를 폼에 다시 채워줌
```terminal
ACCOUNT_PASSWORD_INPUT_RENDER_VALUE = True
```

              
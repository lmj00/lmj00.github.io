---
title: "[Django] 이메일 로그인"
layout: post
categories: Django
---

## 이메일로 로그인
```terminal
ACCOUNT_AUTHENTICATION_METHOD = "email"
```
`user name과 email을 둘 다 허용 하려면 "username_email"`


## 이메일을 필수 항목으로 회원가입, 로그인
```terminal
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_USERNAME = False
``` 


`이메일로 설정 시, Model에 username은 @ 앞 부분이 username으로 사용 되고,`<br/>
`중복된 닉네임이면 랜덤함수를 뒤에 추가한다.` <br/>


## Model의 User인스턴스
```python
def __str__(self):
    return self.email
```
`default는 username이기에 이메일로 바꿔줘야함`
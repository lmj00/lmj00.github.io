---
title: "Connection refused"
layout: post
categories: django
--- 
 
## 문제
회원가입 후 리다이렉트가 생기지 않고 `ConnectionRefusedError at /signup/` 에러가 생겼다.
```terminal
  File "/home/minjin/.pyenv/versions/market-envs/lib/python3.7/site-packages/allauth/account/adapter.py", line 549, in send_confirmation_mail
    self.send_mail(email_template, emailconfirmation.email_address.email, ctx)
  File "/home/minjin/.pyenv/versions/market-envs/lib/python3.7/site-packages/allauth/account/adapter.py", line 140, in send_mail
    msg.send()
  File "/home/minjin/.pyenv/versions/market-envs/lib/python3.7/site-packages/django/core/mail/message.py", line 284, in send
    return self.get_connection(fail_silently).send_messages([self])
  File "/home/minjin/.pyenv/versions/market-envs/lib/python3.7/site-packages/django/core/mail/backends/smtp.py", line 102, in send_messages
    new_conn_created = self.open()
  File "/home/minjin/.pyenv/versions/market-envs/lib/python3.7/site-packages/django/core/mail/backends/smtp.py", line 62, in open
    self.connection = self.connection_class(self.host, self.port, **connection_params)
```
터미널을 보니 회원가입 시 메일로 인증을 보내는 부분에서 문제가 생긴 것 같았다.


## 원인
이메일 세팅을 주석 처리하고, 이메일을 smtp 서버로 보냈기 때문
```terminal
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
```


## 해결 방법
EMAIL_BACKEND 세팅을 smtp가 아닌 console로 바꾸면 된다.<br>
console 값이 기본값이기 때문에 지워도 된다.
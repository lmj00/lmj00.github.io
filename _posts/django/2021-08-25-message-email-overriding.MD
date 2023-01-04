---
title: "메시지, 이메일 오버라이딩"
layout: post
categories: django
---

- app name은 allauth 보다 위에 있어야 한다.


- allauth는 로그인, 로그아웃, 비밀번호 재설정 등 액션이 있을 때 마다 메세지가 생성되는데, <br/>
사용하지 않을 경우 메세지가 계속 쌓이게 된다.`


- 메세지 비활성화를 하는 방법은, 메세지 템플릿을 빈 템플릿으로 오버라이딩하면 된다. <br/>
`templates/account/messages/에 빈 템플릿으로 넣는다.`


- allauth가 발송한 이메일 내용도 같은 방법으로 바꾸면 된다. <br/>
`templates/account/email/에 빈 템플릿으로 넣는다.`


- django template language는 모든 텍스트 기반 폼에서 사용 가능


- allauth가 발송하는 이메일 제목은 오버라이딩을 해도 도메인이 앞에 붙기 때문에 <br/>
`settings에 가서 ACCOUNT_EMAIL_SUBJECT_PREFIX = ""`

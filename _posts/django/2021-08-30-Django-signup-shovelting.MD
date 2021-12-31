---
title: "[삽질] Django 회원가입"
layout: post
categories: Django
---

allauth에 제공하는 기본 폼으로 했을 땐 가입이 잘 됐는데, <br/><br/>
signup.html을 새로 만들고 회원가입 폼을 입력 후, 가입하기를 누르면 아무런 반응이 없었다. <br/><br/>
이것 저것 만져보다가 settings.py에 `ACCOUNT_USERNAME_REQUIRED = False`를 <br/><br/>
`ACCOUNT_USERNAME_USERNAME = False`으로 잘못적은 것을 확인했다. <br/><br/>
default 값은 True라서 유저 네임을 입력을 받는 상태였는데, 여전히 True로 되어 있어서 
폼에서 넘어가지 않았던 것 같다.

---
title: "[Django] CSRF"
layout: post
---

## CSRF(Cross-Site Request Forgery)
- 사용자가 웹 사이트에서 서버로 요청을 보내는 행위를 공격자가 악의적으로 변경하여 전송


## 위조 방지 토큰
- 서버로부터 폼을 요청할 때 발행되어 유저가 서버로 데이터를 전송할 때, 토큰 값과 함께 전달해서 토큰 값을 비교한 뒤 요청을 처리하는 방식 


## Django CSRF 방지
```django
<form>{% raw %}{% csrf_token %}{% endraw %}
...
</form>
```

---
title: "[Django] session"
layout: post
---

## 쿠키 지속 시간
```terminal
SESSION_COOKIE_AGE = {초}
```
`default 값은 2주, 단위는 초`


## 만료된 세션 지우기
```terminal
python manage.py clearsessions
```

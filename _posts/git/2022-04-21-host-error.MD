---
title: "Could not resolve host: github.com"
layout: post
categories: git
--- 


git push가 되지 않고 다음과 같은 오류가 떴다. 
```terminal
$ fatal: unable to access 'https://github.com/lmj00/django-project.git/': Could not resolve host: github.com
```

## 해결 방법
```terminal 
$ sudo vim /etc/resolv.conf
```
`입력 후에 nameserver {기본 게이트웨이}`

---
title: "template extends"
layout: post
categories: django
--- 


### 부모 템플릿
```django
{% raw %}{% load static %}
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title></title>
</head>
<body>
    ...
    {% block {이름} %}
    {% endblock {이름} %}{% endraw %}
</body>
</html>
```


### 자식 템플릿에서 상속
```django
...
{% raw %}{% extends './base.html' %}
{% load static %}
{% block {이름} %}
    <div>...</div>
{% endblock {이름} %}{% endraw %}
    
```
- extends는 첫 줄에 
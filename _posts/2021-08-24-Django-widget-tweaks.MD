---
title: "[Django] widget-tweaks"
layout: post
---

### input 태그에 속성 추가
1. pip install django-widget-tweaks
2. INSTALLED_APPS에 "widget_tweaks"
3. 템플릿으로 가서 {% raw %} {% load widget_tweaks %} {% endraw %} 추가

```django
{% raw %}{{ form.email|attr:"class:{클래스 이름}" }} 또는
{{ form.email|add_class:"{클래스 이름}" }} {% endraw %}
```


## error class 추가하기
```django
{% raw %}{{ form.email|add_error_class:"error" }}{% endraw %}
```


## 에러 메세지
```django
{% raw %}{% for error in form.{필드}.errors %}
    <div class="~~">{{ error }}</div>
{% endfor %}{% endraw %} 
```



---
title: "[Django] widget-tweaks"
layout: post
categories: Django
---

### input 태그에 속성 추가
1. pip install django-widget-tweaks
2. INSTALLED_APPS에 "widget_tweaks"
3. 템플릿으로 가서 {% raw %} {% load widget_tweaks %} {% endraw %} 추가

```django
{% raw %}{{ form.{name}|add_class:{class name}|attr:"placeholder:~~"}} {% endraw %}
```


## error class 추가하기
```django
{% raw %}{{ form.{name}|add_error_class:"error" }}{% endraw %}
```


## 에러 메세지
```django
{% raw %}{% for error in form.{name}.errors %}
    <div class="~~">{{ error }}</div>
{% endfor %}{% endraw %} 
```



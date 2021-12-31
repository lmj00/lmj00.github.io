---
title: "[Django] non-field error"
layout: post
---

## 폼 전체에 대한 오류 접근

```django
{% raw %}{% for error in form.non_fields_errors %}
    <div class="~~">{{ error }}</div>
{% endfor %}{% endraw %}
```

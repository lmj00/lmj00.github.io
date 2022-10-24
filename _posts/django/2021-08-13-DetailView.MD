---
title: "[Django] DetailView"
layout: post
categories: Django
---

## views
```python
from django.views.generic import DetailView

class PracticeDetailView(ListView):  
    model = {사용할 모델}
    template_name = {사용할 템플릿}
    pk_url_kwarg = 'page_id' # urls에서 받은 id
    context_object_name = 'diary'
``` 

 
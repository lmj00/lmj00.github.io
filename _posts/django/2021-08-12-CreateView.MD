---
title: "CreateView"
layout: post
categories: django
---

```python
from django.views.generic import CreateView 
from django.urls import reverse

class PracticeCreateView(CreateView): # CreateView 상속
    model = {사용할 모델}
    form_class = {사용할 폼}
    template_name = 'diary/page_form.html' 
    
    def get_success_url(self):
        return reverse({page-detail}, kwargs={'page_id':self.object.id})
``` 
`변수에 값을 할당하면 제네릭 내부적으로 알게 됨`<br/>
`context를 적어주지 않아도, 키워드 form으로 템플릿에 전달`

- URL 네임(page-detail)으로 거슬러 올라가서 URL을 찾는다.
- kwargs는 keyword argument의 약자, 사전형으로 키워드를 이용해서 값을 전달할 때 사용하는 인자
- self.object는 생성된 Post 데이터 객체에 접근
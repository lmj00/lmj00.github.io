---
title: "[Django] Pagination"
layout: post
---

## Pagination 속성

| 속성 | 설명 | 
| {paginator}.get_page(number) | 번호를 받고 해당 페이지를 리턴, 음수거나 페이지 수보다 크면 마지막 페이지 반환 | 
| {paginator}.count | 모든 페이지의 데이터 개수 |
| {paginator}.num_pages | 총 페이지 수 |
| {page}.has_next() | 다음 페이지가 있으면 True 반환 |
| {page}.has_previous() | 이전 페이지가 있으면 True 반환 |
| {page}.has_other_pages() | 이전 또는 다음 페이지가 있으면 True 반환 |
| {page}.next_page_number() | 다음 페이지 번호 반환 |
| {page}.previous_page_number() | 이전 페이지 번호 반환 |
 

 

## Pagination View
```python
from django.core.paginator import Paginator
from .models import Page (Model class)

def page_list(request):
    pages = Page.object.all()
    paginator = Paginator(pages, 페이지에 보여질 데이터 수)
    page_number = request.GET.get('page') # 쿼리 스트링으로 조회
    page_object = paginator.page(page_number) # 번호에 해당하는 페이지 
    return render(request, '~~.html', {'page_object':page_object})
```

## Pagination Template
```django
{% raw %}{% if page_object.has_previous %}{% endraw %}
{% raw %}    <a href="?page=1">first</a>{% endraw %}
{% raw %}    <a href="?page={{ page_object.previous_page_number }}">prev</a>{% endraw %}
{% raw %}{% end if %}{% endraw %}


{% raw %}{% if page_object.has_next %}{% endraw %}
{% raw %}    <a href="?page={{ page_object.next_page_number }}">next</a>{% endraw %}	
{% raw %}    <a href="?page={{ page_object.paginator.num_pages }}">last</a>{% endraw %}
{% raw %}{% end if %}{% endraw %}

```
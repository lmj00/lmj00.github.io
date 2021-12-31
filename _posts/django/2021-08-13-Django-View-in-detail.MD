---
title: "[Django] View를 간편하게"
layout: post
---

## model 데이터	

| ListView | 'object_list' | '{모델명}_list' | 
|DetailView|'object'|'{모델명}'|
|CreateView| | |
|UpdateView|'object'|'{모델명}'|
|DeleteView|'object'|'{모델명}'|

`context_object_name을 정해주지 않으면 {모델명}, {모델명_list} 값으로 전달한다`

## ListView
- template_name의 기본 값은 모델을 따라간다.</br>
ListView의 템플릿은 {모델명}_list인데, 모델명을 기준으로<br>
템플릿 형식({모델명}_list.html)을 만들면 적어주지 않아도 된다.
- context_object_name을 적지 않아도 django가 object_list와 모델명을 보고 유추 후, 전달
- page_kwrag도 쿼리스트링을 통해 인식


## DetailView
- template_name도 위와 동일
- pk_url_kwarg는 기본 값이 pk다. path에서도 기본 값을 쓰기 위해 pk로 받아야 함. <br/>
이렇게 되면 pk_url_kwarg를 적어주지 않아도 된다.
- context_object_name도 위와 동일


## CreateView
- template_name 위와 동일
- get_success_url에 있는 id도 'pk'로 변경, path도 pk로 수정


## UpdateView
- template_name 위와 동일
- pk_url_kwarg 위와 동일
- get_success_url 위와 동일


## DeleteView
- context_object 위와 동일


## RedirectView
```python
class IndexRedirectView(RedirectView):
    pattern_name = 'page-list'


`상황에 따라 함수형 뷰, 제네릭을 선택`
---
title: "render, redirect, reverse"
layout: post
categories: django
--- 
 
헷갈려서 작성했다.

## [render](https://docs.djangoproject.com/en/4.0/topics/http/shortcuts/#django.shortcuts.render)
HttpResponse 렌더링 된 텍스트와 함께 객체를 반환
```django
render(request, template_name, context = None, content_type = None, status = None,
using = None) 
```
필수 파라미터
- request
- template_name


## [redirect](https://docs.djangoproject.com/en/4.0/topics/http/shortcuts/#django.shortcuts.redirect)
```django
redirect(to, *args, permanent=False, **kwargs)
```
- to에 이동할 URL을 적어주면 된다. 


## [reverse](https://docs.djangoproject.com/en/4.0/ref/urlresolvers/#reverse)
```django
reverse(viewname , urlconf = None , args = None , kwargs = None , current_app = None)
```
<br>
url 템플릿 태그(아래)와 비슷하게 동작
```django
path('archive/', views.archive, name='news-archive')
```
<br>
view에서 생성된 object의 id를 post_id로 url에 넘겨준다.
```django
return reverse('post-detail', kwargs={'post_id': self.object.id}) 
```

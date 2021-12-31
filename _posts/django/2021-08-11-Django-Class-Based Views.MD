---
title: "[Django] Class-Based Views"
layout: post
---

## 클래스형 뷰
- django는 상속 및 mixins를 활용하여 코드를 재사용할 수 있다.
- CRUD에 해당하는 클래스 뷰를 제공한다.

```python
class PracticeCreateView(View):
    def get(self, request):
        ~~
    
    def post(self, request):
        ~~
```
`파이썬 클래스 네이밍은 파스칼 표기법을 사용`<br/>
`urls에 해당하는 path를 views.PracticeCreateView.as_view() 형식으로 써야 함`
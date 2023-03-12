---
title: "클래스형 뷰 - 조회, 생성"
layout: post
categories: drf
---


## 조회, 생성
```python
from rest_framework.views import APIView
...

class SnippetList(APIView):
    def get(self, request):
        snippets = Snippet.objects.all()
        serializer = SnippetSerializer(snippets, many=True)
        return Response(serializer.data)
        
    def post(self, request):
        serializer = SnippetSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
```
- 클래스에 함수를 추가 했기 때문에 self 파라미터를 받음
- status의 기본 값은 200이기 때문에 get함수에서 status 값을 지움

<br>

```python
urlpatterns = [
    path('snippets', SnippetList.as_view()),
]
```
- urls.py에선 view를 호출   
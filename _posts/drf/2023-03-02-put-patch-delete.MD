---
title: "serializer - 수정, 삭제"
layout: post
categories: drf
--- 


## PUT, PATCH
PUT 
- 모든 필드에 대한 수정

PATCH
- 수정할 필드에 대한 값만 전달


## serializer - 수정, 삭제
```python
# urls.py
# django처럼 url로 pk를 받아온다.
urlpatterns = [
    path('snippet/<int:pk>', snippet_list),    
]

# views.py
from rest_framework.generics import get_object_or_404

@api_view(['GET', 'PATCH', 'DELETE'])
def snippet_detail(request, pk):
    snippet = get_object_or_404(Snippet, pk=pk)
    
    ...

    if request.method == 'PATCH':
        serializer = SnippetSerializer(snippets, data=request.data, partial=True) 
        if serializer.is_valid():
            serializer.save()    
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        movie.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
        
partial - PATCH를 사용할 때 필요한 옵션
```

```python
# serializers.py
class SnippetSerializer(serializers.Serializer):
    ...

    # instance는 수정할 데이터
    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.content = validated_data.get('content', instance.content)
        instance.created = validated_data.get('created', instance.created)
        instance.save()
        return instance

get()
- 딕셔너리 타입
- key와 기본 값을 받고, key에 맞는 validated_data에 값이 존재하면 수정 요청한 값, 없으면 기존 필드 값으로 수정 

save()
- 새 인스턴스를 생성하거나 기존 인스턴스를 수정
```

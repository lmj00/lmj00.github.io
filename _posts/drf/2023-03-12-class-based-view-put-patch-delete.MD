---
title: "클래스형 뷰 - 수정, 삭제"
layout: post
categories: drf
---


## 수정, 삭제
```python
class SnippetDetail(APIView):
    # 객체 가져오기
    def get_object(self, pk):
        snippet = get_object_or_404(Snippet, pk=pk)
        return snippet    

    def get(self, request, pk):
        snippet = self.get_object(pk)
        serializer = SnippetSerializer(snippet)
        return Response(serializer.data)
    
    def patch(self, request, pk):
        snippet = self.get_object(pk)
        serializer = SnippetSerializer(snippet, data=requset.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.save()    
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        snippet = self.get_object(pk)
        snippet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
```


## `is_valid(raise_exception=True)`
- serializer 데이터에 에러가 있는 경우 serializers.ValidationError 예외를 발생
- 예외는 REST framework에서 제공하는 예외 처리기에 의해 자동으로 처리, 기본 값은 400 에러
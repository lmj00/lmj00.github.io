---
title: "DRF Request, Response"
layout: post
categories: drf
---


## @api_view()
- DRF에서 Django의 HttpRequest, HttpResponse 대신 Request, Response로 요청 처리


## Request
```python
@api_view(['GET', 'POST'])
def snippet_list(request):
    if request.method == 'POST':
        serializer = SnippetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
```
- POST 요청은 Request 객체에 담겨서 전달 된다.
- JSON 형태로 들어온 데이터를 파싱하여 파이썬 딕셔너리로 변환
- 변환된 데이터는 시리얼라이저를 통해 파이썬 객체 형태로 변경


## Response
```python
@api_view(['GET', 'POST'])
def snippet_list(request):
    if request.method == 'GET':
        snippets = Snippet.objects.all()
        serializer = SnippetSerializer(snippets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK) 
```
- GET 요청이 들어오면 조회한 값이 serializer 변수에 담김
- 시리얼라이저는 파이썬 객체 형태로 저장된 데이터를 파이썬 딕셔너리로 변환
- 파이썬 딕셔너리가 응답으로 전달될 때에는 JSON 형태로 다시 변환
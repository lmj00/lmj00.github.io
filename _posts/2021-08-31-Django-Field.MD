---
title: "[Django] Field"
layout: post
---

### 필드에 url
{name} = models.URLField()


### 선택지 중 하나 정하기

```python
{NAME_CHOICES} = [(a, a), (b, b)]
{name} = models.IntegerField(choices={NAME_CHOICES])
```
`튜플 안에 첫 번째 값은 모델 필드에 들어가는 값` <br/>
`두 번째 값은 화면에 보이는 값` 


### 문자열 기반 필드 빈 값 허용
`blank=True`


### 문자열 기반이 아닌 필드를 옵서녈 필드
`blank=True, null=True`


### unique를 사용할 경우
`unique=True, null=True, blank=True`


- Django는 문자열 기반 필드에 값이 없으면 ""를 저장하기 때문에 null=True를 해주지 않아도 됨 <br>
- 문자열 기반이 아닌 필드(IntegerField, DateTimeField)
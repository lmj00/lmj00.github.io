---
title: "Model Meta options"
layout: post
categories: django
modified_date: 2023-01-18
--- 

## [Model Meta options](https://docs.djangoproject.com/en/3.2/ref/models/options/#model-meta-options)

- 모델에서 사용 가능한 Meta options



## db_table
- 데이터베이스 테이블 이름

```python
class Meta:
    db_table = 'music_album'
```


## ordering
```python
class Meta:
    ordering = ['-order_date']
```
`-를 붙이면 내림차순`


```python
class Meta:
    ordering = ['-a', 'b']
```
`a를 내림차순으로 정렬 후, b를 오름차순으로`


## unique_together
```python
class Meta:
    unique_together = ['driver', 'restaurant']
```
`여러 필드를 조합하여 중복이 되면 안될 때 사용`<br>
`driver, restaurant은 예시 필드`



---
title: "Model (Read)"
layout: post
categories: django
---

### 모든 데이터 조회하기
```python
{model}.objects.all()
```


### 세부 데이터 조회하기
```python
{model}.objects.all().values()
```


### 모든 데이터의 특정 값만 보기
```python
{model}.objects.all().values({필드})
```


### 오름차순, 내림차순
```python
{model}.objects.all().order_by({필드}) 
```	 

```python
{model}.objects.all().order_by({-필드}) 
```	
`내림차순은 필드 앞에 -를 붙여 주면 된다.`



### 조건 키워드
```terminal
`필드명__조건키워드 = "조건"
```


### 하나의 데이터 조회 
```terminal
{model}.objects.get()
```
`결과가 두 개 이상이면 에러`



### 여러 데이터 조회
```terminal
{model}.objects.filter()
```
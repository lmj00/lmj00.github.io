---
title: "Model (Update, Delete)"
layout: post
categories: django
---

### 데이터 수정하기
```terminal
data = {model}.objects.get(id=1)
data.(필드) = "수정할 내용"
data.save()
```

### 데이터 삭제하기
```terminal
data = {model}.objects.get(id=2)
data.delete()
```


### 여러 데이터 조회
```terminal
{model}.objects.filter()
```
---
title: "[Django] ImageField"
layout: post
categories: Django
modified_date: 2022-06-07
--- 

- 폼에 업로드 된 이미지를 media root로 넣어줌

- 사용하려면 pillow라는 이미지 라이브러리 패키지 설치

- 만약 같은 이름의 파일이 이미 있다면 뒤에 랜덤한 값을 추가해서 이름이 중복되지 않게 업로드함.

``` terminal
$ pip install pillow 
```

``` terminal
$ image1 = models.ImageField(upload_to="{업로드 경로}")
```

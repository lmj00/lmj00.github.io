---
title: "[Django] ImageField"
layout: post
categories: Django
--- 

- 폼에 업로드 된 이미지를 media root로 넣어줌

- 사용하려면 pillow라는 이미지 라이브러리 패키지 설치

`pip install pillow`  

`image1 = models.ImageField(upload_to="{업로드 경로}")`
 
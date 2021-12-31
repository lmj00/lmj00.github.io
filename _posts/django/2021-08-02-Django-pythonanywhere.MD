---
title: "[Django] pythonanywhere"
layout: post
categories: Django
---

## bash 
1. unzip {폴더}


2. virtualenv --python=python3.7 {가상 환경 이름}


3. cd {가상 환경 이름}


4. source bin/activate


5. pip install django==2.2


6. 오른쪽 상단 web 클릭


## web
1. 왼쪽에 add를 눌러서 웹 앱 생성


2. Manual configuration 


3. python 버전 선택


4. Source code 경로 수정
```terminal
/home/{자신의 id}/{프로젝트명}
```


5. WSGI 설정
`19 ~ 47 주석 처리, 76 ~ 89 주석 해제`
`81 path에서 mysite 부분을 {프로젝트명}으로 바꿔줌`
`85 '{프로젝트명}.settings'으로 바꿔줌`


6. web으로 이동 후, Virtualenv 경로 수정
`/home/{자신의 id}/{가상 환경 이름}`


7. static 경로 설정
`URL은 /static/`
`Directory는 /home/minjin/costaruant/static`


8. Reload 후 접속
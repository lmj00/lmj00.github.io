---
title: "Django REST Framework"
layout: post
categories: drf
--- 


## DRF(Django REST Framework)
- 풀스택 프레임워크인 Django와 달리 DRF는 Django를 백엔드 개발에만 사용하게 해준다.


## 직렬화
- Django에서 백엔드의 데이터는 파이썬 객체로 사용하고 프론트엔드에서는 JSON으로 사용한다. 서로 통신하기 위해 데이터 형식을 통일하는 것을 DRF가 해준다.
- 직렬화는 파이썬 객체로 저장된 데이터를 JSON으로, 역직렬화는 JSON 형태의 데이터를 파이썬 객체로 바꿔주는 것이다.


## REST(Representational State Transfer)
- API를 만들 때 따라야 하는 소프트웨어 아키텍처
- 아키텍처 스타일의 원칙은 균일한 인터페이스, 무상태, 계층화 시스템, 캐시 가능성, 온디맨드 코드, 클라이언트-서버로 구성되어 있다.


## REST URL 규칙
- 마지막 부분에 슬래시를 사용하면 안된다.
- 언더바 대신 하이픈을 사용
- 소문자 사용
- 확장자를 사용하면 안된다.
- CRUD에 대한 행위를 포함시키면 안된다.

	
## API(Application Programming Interface)
- 다른 소프트웨어 시스템과 통신하는 방법을 정의한다.

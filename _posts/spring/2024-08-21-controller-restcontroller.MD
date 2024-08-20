---
title: "Controller / RestController"
layout: post
categories: spring
--- 


### Controller
- 일반적으로 @RequestMapping과 함께 사용
- 뷰를 반환해야 할 때 가장 적합
- Model 객체와 함께 사용


### RestController
- Spring 4.0에 도입된 RESTful 웹 서비스를 구축하는 Spring 접근 방식
- @Controller와 @ResponseBody를 모두 포함하는 축약형 어노테이션
- 모든 메서드가 뷰(HTML, thymeleaf, JSP) 대신 도메인 객체를 반환
- 반환 객체를 자동으로 HttpResponse로 직렬화
- `spring-boot-starter-web` 의존성에 Jackson 라이브러리가 존재하기에 자동으로 인스턴스를 JSON으로 변환한다.


## 참고
- [Building a RESTful Web Service](https://spring.io/guides/gs/rest-service)
- [Annotation Interface RestController](https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/web/bind/annotation/RestController.html)
- [The Spring @Controller and @RestController Annotations](https://www.baeldung.com/spring-controller-vs-restcontroller)
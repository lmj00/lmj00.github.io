---
title: "스프링 입문"
layout: post
categories: spring
--- 


### Spring
> 웹 어플리케이션의 첫 진입점이 Controller

> Spring Boot는 톰캣이라는 웹서버를 내장하고 있다.

<br>

웹 개발을 할 때 크게 3가지 방법이 있다.

- 정적컨텐츠
- MVC와 템플릿 엔진
- API


### 정적컨텐츠
> 서버에서 웹 브라우저에 파일을 그대로 내려줌

```java
@Controller
public class HelloController {

    @GetMapping("hello")
    public String hello(Model model) {
        model.addAttribute("data", "hello");
        return "hello";
    }
}
```
1. 웹 브라우저에서 localhost/hello-static.html을 접속한다.
2. 내장 톰캣 서버가 요청을 받음
3. 스프링으로 넘기기 전에 hello-static과 관련된 컨트롤러가 있는지 확인한다.
4. 없으면 resources/static/hello-static.html을 웹 브라우저로 반환한다.

> Spring이 model을 하나 만들어서 넘겨준다.

> model.addAttribute를 통해 key-value 형태로 넘겨준다.

> return에 적은 곳으로 렌더링

> resourses/templates 밑에 있는 hello.html을 찾게된다.


### MVC와 템플릿 엔진
> 서버에서 변형하여 HTML을 내려준다.
 
> MVC가 등장하기 이전에는 Model1 방식(View에서 모든 것을 처리함)

> View - 화면에 그리는 데 집중

> Model, Controller - 비즈니스 로직, 내부 처리에 집중

```java
@Controller
public class HelloController {

    @GetMapping("hello-mvc")
    public String helloMvc(@RequestParam("name") String name, Model model) {
        model.addAttribute("name", name);
        return "hello-template";
    }
}
```

1. 웹 브라우저에서 localhost/hello-mvc를 접속한다.
2. 내장 톰캣 서버가 요청 받음, 톰캣 서버가 hello-mvc라는 것이 왔다고 스프링에게 전달
3. 스프링은 hello-mvc로 맵핑된 컨트롤러가 있는 걸 확인, 이 메서드를 호출
4. 리턴을 해줄 때 viewResolver가 hello-template으로 반환 
5. 템플릿 엔진(Thymeleaf)이 렌더링해서 변환한 HTML을 웹 브라우저에 반환

viewResolver - 뷰를 찾아주고 템플릿으로 연결


### API
```java
@Controller
public class HelloController {

    @GetMapping("hello-api")
    @ResponseBody
    public Hello helloApi(@RequestParam("name") String name) {
        Hello hello = new Hello();
        hello.setName(name);
        return hello;
    }


    static class Hello {
        private String name;

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

    }
}
```

1. 웹 브라우저에서 localhost/hello-api를 접속한다.
2. 내장 톰캣 서버가 요청을 받음, 톰캣 서버가 hello-api라는 것이 왔다고 스프링에게 전달
3. 스프링은 hello-api로 맵핑된 컨트롤러가 있는 걸 확인하는데, ResponseBody이라는 어노테이션이 붙어있는 걸 발견
4. ResponseBody가 있으면 HTTP의 응답에 데이터를 넣어 동작
5. 문자열이면 그대로 응답하면 되지만, 객체일 때는 JSON 방식으로 데이터를 만들어서 HTTP 응답에 반환하는 게 기본 정책

> 스프링에서 ResponseBody의 기본은 JSON 반환

> 객체를 넘기면 HTTP의 메시지 컨버터가 동작한다. 단순 문자열이면 StringConverter이 동작, 객체면 JsonConverter라는게 동작한다. JsonConverter는 객체를 JSON으로 바꾸고, 요청한 웹브라우저나 서버한테 JSON으로 보내준다.

> HTTP Accept 헤더에 JSON이라고 요청이 오면 JSON으로 받고, 아무것도 안 보내면 다 받을 수 있다.
아무것도 안 보내면 스프링이 알아서 요청한 형식으로 보낸다.

> getter setter는 자바 빈 규약 또는 프로퍼티 접근 방식이라고도 한다.

---
 
### 참고
[[김영한] 스프링 입문 - 코드로 배우는 스프링 부트, 웹 MVC, DB 접근 기술](https://www.inflearn.com/course/%EC%8A%A4%ED%94%84%EB%A7%81-%EC%9E%85%EB%AC%B8-%EC%8A%A4%ED%94%84%EB%A7%81%EB%B6%80%ED%8A%B8/dashboard)
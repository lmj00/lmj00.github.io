---
title: "thymeleaf pagination"
layout: post
categories: spring
--- 

thymeleaf에서 페이징을 구현하는데 다음과 같은 오류가 떴다.

```java
th:with="start=${T(Math).floor(..."
>>> EL1005E: Type cannot be found Math
```
<br>
버전이 업데이트 되면서 클래스를 호출하는 방법이 바뀌었다.
[https://github.com/thymeleaf/thymeleaf/issues/872](https://github.com/thymeleaf/thymeleaf/issues/872)<br>
[https://github.com/thymeleaf/thymeleaf/issues/873](https://github.com/thymeleaf/thymeleaf/issues/873)<br>
[https://github.com/thymeleaf/thymeleaf/issues/878](https://github.com/thymeleaf/thymeleaf/issues/878)

<br>
아래와 같은 방법으로 작성해야 한다.
```java
th:with="start=${T(java.lang.Math).floor(..."
``` 
현재는 페이징 로직을 View에서 처리했지만, 좋지 않은 방법이라고 한다. <br>
필요한 로직은 Controller에서 처리 후 View로 넘겨주는 방법으로 사용해야한다.





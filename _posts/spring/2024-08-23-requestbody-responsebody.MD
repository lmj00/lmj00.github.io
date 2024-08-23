---
title: "RequestBody / ResponseBody"
layout: post
categories: spring
--- 


### RequestBody
- HttpRequest body를 도메인 객체에 매핑하여 Java 객체로 자동으로 역직렬화
- POST, PUT, PATCH 메서드와 함께 사용

```java
@Data
@Builder
public class SearchRequestDto {
    private List<String> value;
}
```

```java
@RestController
@RequiredArgsConstructor
public class SearchController {
    private final SearchService searchService;
    
    @PostMapping("/getSearch")
    public ResponseEntity<List<SearchResponseDto>> getSearch(@RequestBody SearchRequestDto searchRequestDto) {
        return ResponseEntity.ok(searchService.getSearch(searchRequestDto));
    }   
}
```

```java
@Service
@RequiredArgsConstructor
public class SearchService {
    
    private final SearchRepository searchRepository;

    public List<SearchResponseDto> getSearch(SearchRequestDto searchRequestDto) {
        List<SearchResponseDto> returnValue = new ArrayList<>();
        
        List<Search> searchValues = searchRepository.getSearch(searchRequestDto.getValue());

        for (Search search : searchValues) {
            returnValue.add(new SearchResponseDto(search));
        }

    return returnValue;

    }
}
``` 

### ResponseBody
- 객체를 JSON으로 직렬화하여 HttpResponse 객체로 다시 전달
- @RestController를 사용할 때, 해당 어노테이션이 포함되어 있어서, 주로 @Controller와 사용된다.


### 참고
- [Spring’s RequestBody and ResponseBody Annotations](https://www.baeldung.com/spring-request-response-body)
- [Difference Between @RequestBody and @ResponseBody Annotation in Spring](https://www.geeksforgeeks.org/difference-between-requestbody-and-responsebody-annotation-in-spring/)
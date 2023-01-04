---
title: "Validation"
layout: post
categories: django
---

## 유효성 검사
- 입력 데이터의 규격이 맞는지 확인하는 과정
- 크게 두 가지 방법(Field, Validator)

 
## Field  
```django
Form.is_valid()
```
`데이터의 유효성을 검사 후, bool을 반환`  


## Validator
- 값을 받아서 ValidationError 기준에 충족하지 않으면 에러를 발생시키는 함수
- 여러 필드에서 사용가능
- Django에서 제공하는 Built-in Validator를 사용하거나, 직접 Validator 구현 가능  


### Built-in Validator
- django.core.validators를 import 해서 사용  
```django
models.CharField(validators=[MinLengthValidator(10, 'error message'])
```   


- 함수를 만든 후 사용
```django
models.~~Field(validators[함수])
```


## Form
- Model을 쓰지 않는 일반 form의 경우 사용
- validator, clean_{field_name}을 사용
```django
def clean_title(self):
    title = self.cleaned_data['title']
    if ~~~:
        raise ValidationError('error message')
```
`모든 form class는 cleaned_data를 가지고 있는데,  
이 안에는 form 필드를 정의할 때 넣어준 유효성 검증을 통과한 데이터가 들어 있다.`
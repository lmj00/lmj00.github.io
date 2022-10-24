---
title: "[Django] 관계형 모델(1:N)"
layout: post
categories: Django
--- 

### 1:N
`{name} = models.ForeginKey({model})`


### 참조하는 오브젝트가 삭제되었을 때 처리 방법
`{fk_name} = models.ForeginKey({model}, on_delete=models.{option})` <br/><br/>

#### CASCADE
- 계단식 삭제, 참조하는 객체도 삭제

#### PROTECT
- ProtectedError를 발생시켜 객체 삭제 방지

#### SET_NULL
- ForeignKey를 null로 설정, null=True일 경우만 사용 가능

#### SET_DEFAULT
- ForeignKey를 default로 설정 

#### SET()
- ForeignKey에 전달된 값으로 설정하거나 함수 호출

#### DO_NOTHING
- 아무런 행동도 하지 않음


### object filter
`{model}.objects.filter({fk_name}__{필드명}={1})`






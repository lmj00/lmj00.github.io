---
title: "ModelSerializer"
layout: post
categories: drf
--- 


## [ModelSerializer](https://www.django-rest-framework.org/api-guide/serializers/#modelserializer)
```python
class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'account_name', 'users', 'created']        
```
- create()와 update()의 함수를 직접 정의하지 않고 간단하게 구현이 가능하다.


## Meta
모든 필드 적용시 
```python 
field '__all__'
```

<br>

read_only 지정
```python
read_only_fields = ['account_name']
```
- AutoField는 자동으로 read_only로 설정된다. 

<br>

필드 제외
```python
exclude = ['users']
```
- fields나 exclude중 하나를 필수로 사용해야 한다.

<br>

필드 추가
```python
extra_kwargs = {'password': {'write_only': True}}
```
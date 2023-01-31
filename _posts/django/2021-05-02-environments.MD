---
title: "개발 환경 구성"
layout: post
categories: django
modified_date: 2023-02-01
---

### pyenv로 설치할 수 있는 버전 보기
```python
pyenv install --list
```


### pyenv로 python 설치 
```python
pyenv install 3.8.2
```


### 가상 환경 생성
```python
pyenv virtualenv {파이썬 버전} {가상 환경 이름}
```


### 가상 환경 삭제
```python
pyenv uninstsall {가상 환경 이름}
```


### 버전 확인
```python
pyenv versions
```


### 가상 환경 적용
```python
pyenv global {가상 환경 이름}
pyenv local {가상 환경 이름}
```


### 설치되어있는 패키지 목록 확인
```python
pip list
```

## django 설치
```python
pip3 install django=={버전}
```
`사용할 환경에 django를 설치해야 함`


## 설치 확인
```python
django-amdin --version
```


## WSL 폰트
- [d2coding](https://github.com/naver/d2codingfont)
1. 검색 -> 글꼴 설정
2. WSL 우 클릭으로 속성 들어가서 지정


## WSL에 윈도우 파일 넣기
```terminal
explorer.exe .
```
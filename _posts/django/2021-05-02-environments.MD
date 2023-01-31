---
title: "개발 환경 구성"
layout: post
categories: django
modified_date: 2023-02-01
---

## pyenv로 설치할 수 있는 버전 보기
```python
pyenv install --list
```


## pyenv로 python 설치 
```python
pyenv install 3.8.2
```


## 가상 환경 생성
```python
pyenv virtualenv {파이썬 버전} {가상 환경 이름}
```


## 가상 환경 삭제
```python
pyenv uninstsall {가상 환경 이름}
```


## 버전 확인
```python
pyenv versions
```


## 가상 환경 적용
```python
pyenv global {가상 환경 이름}
pyenv local {가상 환경 이름}
```


## 설치되어있는 패키지 목록 확인
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


## Zsh Shell
```shell
sudo apt-get install zsh
chsh -s `which zsh`
echo $SHELL
```


## Oh-My-Zsh
```shell
sh -c "$(curl -fsSL https://raw.github.com/robbyrussell/oh-my-zsh/master/tools/install.sh)"
```


## pyenv 설정
```shell
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv virtualenv-init -)"
```
- 기존의 pyenv 설정은 bash shell에 설정한 것이므로 zsh shell인 .zshrc에도 설정
- pyenv versions으로 설정이 됐는지 확인



## zsh-syntax-highlighting 
```shell
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git
```
```shell
echo "source ${(q-)PWD}/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" >> ${ZDOTDIR:-$HOME}/.zshrc
```



## zsh-autosuggestions
```shell
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
```
`code .`로 .zshrc를 열어서  plugins=(git) 옆에 한 칸 띄우고 추가
```shell
plugins=(git zsh-autosuggestions)
```

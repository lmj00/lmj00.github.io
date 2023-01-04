---
title: "Remote Repository"
layout: post
categories: git
--- 

## origin
```terminal
$ git remote add origin https://github.com/lmj00/lmj00.github.io
```
- 위의 retmote repository를 origin 이라는 이름으로 등록하겠다 
- remote repository를 최초로 추가할 때 origin의 이름으로 가리키는 것이 git 관례
 

## push
```terminal
$ git push -u origin master		
```
- local respository에 있는 master 브랜치의 내용을 origin이라는 remote repository로 보내겠다
- master 브랜치가 없으면 생성 후 push 
- -u는 --set-upstream의 약자
- -u 옵션을 주면 local repository에 있는 브랜치가 origin에 있는 master 브랜치를 추적


 



 
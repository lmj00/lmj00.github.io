---
title: "Branch merge, conflict"
layout: post
categories: git
--- 

## merge
`A branch에서 B branch를 merge하면`<br>
`B branch에서 했던 커밋들을 가져올 수 있다`


```terminal
$ git merge master
```


## conflict
- merge를 하다가 충돌이 발생
- git이 어느 것을 반영해야 할 지 결정할 수 없을 때 발생
 

## merge 취소
```terminal
$ git merge --abort
```
`abort: 취소하다, 중단하다`<br>
`conflict가 없어지고 , merge를 하기 전으로 돌아감`


## 여러 파일에서의 conflict
- 파일 하나씩 conflict를 해결하면서 git status로 확인 후, git add

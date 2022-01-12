---
title: "[Git] revert"
layout: post
categories: Git
--- 
 
## revert
```terminal
$ git revert {커밋 해시}
```
- 실행하면 커밋 메시지 창이 뜬다. 해당 커밋 이전으로 되돌릴 수 있다. <br>
push를 하면 이전 커밋으로 되돌아간다.


## 왜 reset을 사용하면 안되는가?
- local repository에서 reset을 하게 되면, remote repository가 더 최신 커밋이기 때문에 <br>
git pull을 해야된다. 
- revert를 사용하게 되면 local repository에서 이후의 커밋이 생기기 때문에 push가 가능하다.


## 여러 커밋 revert
```terminal
$ git revert {커밋 해시 1}..{커밋 해시 2}
```
`1번 커밋은 포함되지 않는다`

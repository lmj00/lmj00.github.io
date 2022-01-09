---
title: "[Git] HEAD와 branch"
layout: post
categories: Git
--- 


## HEAD
- 커밋을 가리키는 것이 아닌 branch를 가리킴
- master branch를 통해 간접적으로 커밋을 가리킴
- 만약 B branch로 가게 되면 HEAD가 master에서 B branch를 가리킴


## branch
- branch도 HEAD처럼 커밋을 가리키는 존재
- 커밋은 이전 커밋에 대한 정보를 가지고 있다.


## git checkout
- HEAD가 커밋을 직접 가르킬 수 있게 함
- branch를 직접 가리킬 수 있게 함
```terminal
$ git checkout {브랜치 이름}
```


## Detached HEAD
- `git checkout a12b`를 하게 되면 branch를 통해서 커밋을 가리키는 게 아닌 HEAD가 직접 커밋을 가리킴
- 과거 커밋에서 새로운 branch를 만들고 싶을 때 사용



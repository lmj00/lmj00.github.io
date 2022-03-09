---
title: "[Git] rebase"
layout: post
categories: Git
--- 
 

## rebase
- 현재 브랜치의 베이스를 대상 브랜치로 재지정 
```terminal
$ git rebase {대상 브랜치}
```
1. conflict 해결 후 `git add`
2. `git rebase --continue`


### 사용 이유
- merge와 결과는 같다.
- 커밋 히스토리를 깔끔하게 하고 싶을 때 사용
- 세세한 커밋 히스토리를 담고 싶을 땐 `merge` 사용





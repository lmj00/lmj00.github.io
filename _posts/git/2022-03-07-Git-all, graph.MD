---
title: "[Git] all, graph"
layout: post
categories: Git
--- 
 

## all
- 현재 있는 브랜치와 다른 브랜치의 커밋 히스토리를 보려면
```terminal
$ git log --pretty=oneline --all
```


## graph
- 커밋 히스토리를 그래프로 출력
```terminal
$ git log --pretty=oneline --all --graph
```
![image](https://user-images.githubusercontent.com/54443194/156930968-f4efa1f9-cdc6-4d44-806c-a96699484df9.PNG)

- *은 하나의 커밋
- 선이 합쳐지는 부분은 merge 커밋
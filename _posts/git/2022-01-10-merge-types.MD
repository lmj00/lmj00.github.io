---
title: "merge의 종류"
layout: post
categories: git
--- 
 
## Fast-forward merge
- 커밋 히스토리에서 같은 line에 있는 branch를 merge
- 새로운 커밋이 생기지 않고, branch가 이동하게 됨(최신 커밋으로 이동)


## 3-way-merge
1. 두 갈래로 갈라지기 전 공통 조상이 되는 커밋 
2. 한 브랜치가 가리키는 커밋
3. 다른 브랜치가 가리키는 커밋



`위의 3가지 커밋 기준으로 merge 커밋을 자동으로 만듦`

- base 내용과 비교했을 때 달라진 부분이 우선시
- 2개의 branch에서 변화가 일어나서, merge를 하지 못 할 경우, conflict 발생  
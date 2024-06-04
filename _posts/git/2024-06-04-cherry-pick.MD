---
title: "cherry-pick"
layout: post
categories: git
--- 

### [cherry-pick](https://git-scm.com/docs/git-cherry-pick)
특정 커밋을 선택하여 해당 변경사항을 현재 브랜치로 가져온다.

```terminal
$ git cherry-pick [커밋해시]
```

---

### 예시
#### main
![image](https://github.com/lmj00/practice-git/assets/54443194/c770ad23-1748-4d18-a621-1ba8638b1208)


#### dev
![image](https://github.com/lmj00/practice-git/assets/54443194/ab150b37-be71-4b0c-bde8-2f12c386f655)

main 브랜치에 add, subtract, multiply 기능이 있고,

dev 브랜치에 divide, sqrt 기능이 있다.

main <- dev로 merge를 하면 divide, sqrt 기능이 합쳐지게 된다.

만약, sqrt 기능은 필요없고 divide 기능이 필요할 때 `cherry-pick`을 사용하면 된다.

### test
1. 특정 커밋을 선택할 브랜치로 이동한다. (dev)
![image](https://github.com/lmj00/practice-git/assets/54443194/6c1f4191-b00a-4fd8-b509-b3e3e879f719)

2. 현재 divide의 해시는 d6cc

3. 해당 기능을 적용할 브랜치로 이동 (main)

4. `git cherry-pick d6cc`

5. push

<br>

main 브랜치를 확인해보면 sqrt 기능이 빠지고 divide 기능만 적용되었다.


![image](https://github.com/lmj00/practice-git/assets/54443194/90691c31-c330-476f-ba0b-e1b66ab89309)


### options
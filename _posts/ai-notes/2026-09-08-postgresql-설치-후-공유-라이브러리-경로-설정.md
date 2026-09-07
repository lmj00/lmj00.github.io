---
title: "PostgreSQL 설치 후 공유 라이브러리 경로 설정"
layout: post
categories: ai-notes
type: study-note
date: 2026-09-08 08:24:05 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-09-08
sources:
  - https://www.postgresql.org/docs/current/install-post.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: PostgreSQL을 기본 검색 경로 밖에 설치하면 런타임 링커가 `libpq.so` 같은 공유 라이브러리를 찾지 못해 `psql` 실행이 실패할 수 있다. `LD_LIBRARY_PATH`나 `ldconfig`로 라이브러리 위치를 알려주는 방법을 정리한다.

### 개요
PostgreSQL을 소스에서 빌드해 설치하면 `psql`이 실행에 사용하는 `libpq` 같은 공유 라이브러리가 함께 설치된다. 이 라이브러리가 시스템의 기본 검색 경로 밖(예: `/usr/local/pgsql/lib`)에 설치되면, `psql` 같은 프로그램이 실행될 때 런타임 링커가 라이브러리를 찾지 못할 수 있다. PostgreSQL 매뉴얼의 17.5.1 Shared Libraries 절은 이런 상황에서 시스템에 공유 라이브러리 위치를 알려주는 방법을 설명한다.

### 왜 공유 라이브러리 경로 설정이 필요한가
공유 라이브러리를 사용하는 일부 시스템에서는 새로 설치한 라이브러리를 시스템이 찾을 수 있도록 알려줘야 한다. 이 설정을 건너뛰면 `psql` 실행 시 다음과 같은 오류가 나타난다.

```
psql: error in loading shared libraries
libpq.so.2.1: cannot open shared object file: No such file or directory
```

이 오류가 발생했다면 라이브러리 경로 설정이 필요한 상황이라는 뜻이다. 반대로 FreeBSD, Linux, NetBSD, OpenBSD, Solaris에서는 이 설정이 필요하지 않다고 매뉴얼은 안내한다.

![diagram](/assets/diagrams/2026-09-08-postgresql-설치-후-공유-라이브러리-경로-설정-1.svg)

### LD_LIBRARY_PATH로 검색 경로 등록
공유 라이브러리 검색 경로를 설정하는 방법은 플랫폼마다 다르지만, 가장 널리 쓰이는 방법은 `LD_LIBRARY_PATH` 환경 변수를 설정하는 것이다. Bourne 셸 계열(`sh`, `ksh`, `bash`, `zsh`)에서는 다음과 같이 설정한다.

```sh
LD_LIBRARY_PATH=/usr/local/pgsql/lib
export LD_LIBRARY_PATH
```

`csh`나 `tcsh`에서는 다음 명령을 사용한다.

```csh
setenv LD_LIBRARY_PATH /usr/local/pgsql/lib
```

`/usr/local/pgsql/lib` 자리에는 빌드 1단계에서 `--libdir`로 지정한 값을 넣는다. 이 명령은 `/etc/profile`이나 `~/.bash_profile` 같은 셸 시작 파일에 넣어두는 것이 좋다. 이 방법의 주의사항은 `http://xahlee.info/UnixResource_dir/_/ldpath.html`에서 확인할 수 있고, 시스템별 동작이 궁금하면 `ld.so`나 `rld` 매뉴얼 페이지를 참고한다.

### 플랫폼별 대안: LD_RUN_PATH와 Cygwin
일부 시스템에서는 빌드 전에 `LD_RUN_PATH` 환경 변수를 설정하는 편이 더 나을 수 있다. Cygwin에서는 라이브러리 디렉터리를 `PATH`에 넣거나 `.dll` 파일을 `bin` 디렉터리로 옮기는 방식을 사용한다.

### ldconfig로 런타임 링커 캐시 갱신
Linux에서 root 권한이 있다면 설치 후 다음 명령으로 런타임 링커가 공유 라이브러리를 더 빨리 찾도록 할 수 있다. 디렉터리 경로는 설치 위치에 맞게 바꾼다.

```sh
/sbin/ldconfig /usr/local/pgsql/lib
```

FreeBSD, NetBSD, OpenBSD에서는 `-m` 옵션을 붙인다.

```sh
/sbin/ldconfig -m /usr/local/pgsql/lib
```

다른 시스템에는 이에 해당하는 명령이 알려져 있지 않다. `ldconfig`의 자세한 사용법은 해당 매뉴얼 페이지를 참고한다.

### 정리
PostgreSQL을 기본 검색 경로 밖에 설치하면 런타임 링커가 `libpq.so` 같은 공유 라이브러리를 찾지 못해 `psql`이 실행되지 않는다. 가장 일반적인 해결책은 `LD_LIBRARY_PATH`에 `--libdir`으로 지정한 디렉터리를 등록하는 것이고, root 권한이 있다면 Linux에서는 `ldconfig`, FreeBSD·NetBSD·OpenBSD에서는 `ldconfig -m`으로 링커 캐시를 갱신할 수 있다. Cygwin처럼 예외적인 플랫폼은 `PATH`나 `.dll` 배치 방식으로 해결한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/install-post.html](https://www.postgresql.org/docs/current/install-post.html)

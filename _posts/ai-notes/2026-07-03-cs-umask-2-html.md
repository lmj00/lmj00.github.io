---
title: "Cs: Umask.2.Html"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-03
tags: [cs, os, syscall]
generated_by: "openrouter:google/gemma-4-26b-a4b-it:free"
generated_at: 2026-07-03
sources:
  - https://man7.org/linux/man-pages/man2/umask.2.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요

`umask`는 프로세스가 파일을 생성할 때 적용되는 파일 모드 생성 마스크(file mode creation mask)를 설정하는 시스템 호출이다. 새로운 파일이나 디렉토리가 생성될 때 지정된 권한이 자동으로 제거되도록 하여 보안과 권한 관리를 수행한다.

### 동작 원리

`umask()` 시스템 호출은 호출하는 프로세스의 마스크 값을 인자로 전달된 `mask & 0777` 값으로 설정한다. 이때 파일 권한 비트는 마스크의 하위 9비트만 사용된다.

파일 생성 시 권한이 결정되는 과정은 다음과 같다.

![diagram](/assets/diagrams/2026-07-03-cs-umask-2-html-1.svg)

`umask`는 `open(2)`나 `mkdir(2)`와 같이 파일을 생성하는 시스템 호출에서 전달된 `mode` 인자로부터 특정 권한 비트를 제거하는 방식으로 동작한다.

#### ACL(Access Control List)과의 관계
부모 디렉토리에 기본 ACL이 설정되어 있는 경우 `umask`는 무시된다. 이 경우 프로세스는 기본 ACL을 상속받으며, 권한 비트는 상속된 ACL을 바탕으로 설정된다. 만약 `mode` 인자에 포함되지 않은 권한 비트가 있다면 해당 비트는 제거된다.

### 주요 특징 및 범위

`umask` 설정이 영향을 미치는 대상과 범위는 다음과 같다.

| 구분 | 내용 |
| :--- | :--- |
| **영향을 받는 객체** | 파일, 디렉토리, POSIX IPC 객체(`mq_open`, `sem_open`, `shm_open`), FIFO, UNIX 도메인 소켓 |
| **영향을 받지 않는 객체** | System V IPC 객체(`msgget`, `semget`, `shmget`) |
| **프로세스 상속** | `fork(2)`를 통해 생성된 자식 프로세스는 부모의 `umask`를 상속받음 |
| **프로세스 실행** | `execve(2)`를 호출해도 `umask` 값은 변경되지 않고 유지됨 |

### 주의사항 및 제약 사항

`umask()`를 사용할 때 프로그래머가 유의해야 할 몇 가지 기술적 특성이 있다.

**1. 원자적 조회 불가능**
`umask()` 함수는 새로운 마스크 값을 설정함과 동시에 이전 마스크 값을 반환한다. 따라서 현재의 `umask` 값을 단순히 조회하기 위해서는 값을 변경했다가 다시 원래대로 돌려놓는 과정이 필요하다. 이러한 비원자적(non-atomic) 특성 때문에 멀티스레드 환경에서는 경합 조건(race condition)이 발생할 수 있다. 

단, Linux 4.7 이상에서는 `/proc/[pid]/status` 파일의 `Umask` 필드를 확인하여 값을 변경하지 않고도 조회할 수 있다.

**2. 반환 값**
`umask()` 시스템 호출은 항상 성공하며, 설정되기 전의 이전 마스크 값을 반환한다.

### 정리

- `umask`는 파일 생성 시 권한 비트를 마스킹하여 기본 권한을 제한한다.
- `fork` 시 상속되지만 `execve` 시에는 유지된다.
- 값을 조회하려면 새로운 값을 설정해야 하므로 멀티스레드 환경에서 주의가 필요하다.
- Linux에서는 `/proc` 파일 시스템을 통해 안전하게 조회할 수 있는 대안을 제공한다.

---
> 🤖 작성 모델: `google/gemma-4-26b-a4b-it:free` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://man7.org/linux/man-pages/man2/umask.2.html](https://man7.org/linux/man-pages/man2/umask.2.html)

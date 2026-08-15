---
title: "Meson 빌드 시스템으로 PostgreSQL 소스 설치하기"
layout: post
categories: ai-notes
type: study-note
date: 2026-08-16 06:26:06 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-08-16
sources:
  - https://www.postgresql.org/docs/current/install-meson.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요
PostgreSQL은 소스 코드로부터 직접 빌드하여 설치하는 방법을 제공한다. 17.4 버전부터는 기존의 Autoconf/Make 기반 빌드 시스템 외에 **Meson** 빌드 시스템을 사용한 방법이 도입되었다. Meson은 설정 파일(`meson.build`)을 기반으로 빌드 디렉터리를 구성하고, **Ninja**를 주된 빌드 도구로 사용하여 빠르고 효율적인 빌드 프로세스를 제공한다. 이 방식은 개발용 디버그 빌드와 정적 분석용 빌드 등 여러 빌드 구성을 손쉽게 관리할 수 있는 장점이 있다.

### 빌드 및 설치 절차의 개념
Meson을 이용한 PostgreSQL 설치 과정은 크게 **설정(Configure)**, **빌드(Build)**, **테스트(Test)**, **설치(Install)**의 네 단계로 구성된다. 이 과정은 `meson setup` 명령으로 빌드 트리를 초기 구성하는 일회성 작업으로 시작한다.

![diagram](/assets/diagrams/2026-08-16-meson-빌드-시스템으로-postgresql-소스-설치하기-1.svg)

**설정(Configuration)**: `meson setup build` 명령은 필수 인자인 `builddir`(예: `build`)을 받아 빌드 디렉터리를 생성하고 설정을 로드한다. `srcdir`(소스 디렉터리)는 명시하지 않으면 현재 디렉터리와 `meson.build` 파일의 위치로부터 자동 추론된다. 초기 설정 후에는 `meson configure` 명령으로 옵션을 재설정할 수 있다.

**빌드(Build)**: 설정이 완료된 빌드 디렉터리에서 `ninja` 명령을 실행하면 컴파일이 진행된다. Ninja는 시스템의 CPU 코어 수를 자동 감지하여 병렬 처리를 최적화한다. `-j` 옵션으로 병렬 프로세스 수를 직접 지정할 수도 있다. Meson은 소스 트리의 변경 사항을 자동으로 감지하여 재구성하므로, 이후 빌드는 항상 `ninja` 명령만으로 가능하다.

**회귀 테스트(Regression Tests)**: 빌드가 완료된 서버를 설치 전에 테스트하려면 `meson test` 명령을 사용한다. 이 테스트 스위트는 PostgreSQL이 개발자의 기대대로 동작하는지 검증한다. 주의할 점은 **root 권한으로는 실행할 수 없으며**, 일반 사용자 권한으로 실행해야 한다. 이미 실행 중인 postgres 인스턴스에 대해 테스트를 실행하려면 `meson test --setup running` 인자를 사용한다.

**설치(Installation)**: 최종적으로 `ninja install` 명령을 실행하면 **1단계(설정)**에서 지정한 디렉터리들에 파일들이 설치된다. 설치 대상 디렉터리에 대한 쓰기 권한이 필요하므로, 경우에 따라 root 권한이 필요할 수 있다. 설치를 취소하려면 `ninja uninstall`을, 빌드된 파일을 정리하려면 `ninja clean` 명령을 사용할 수 있다.

### 주요 설정 옵션의 이해
`meson setup` 명령에는 PostgreSQL의 설치 위치, 기능, 빌드 세부 사항을 제어하는 다양한 옵션이 존재한다. 옵션은 `--`로 시작하는 Meson 공통 옵션과, PostgreSQL 특화 기능을 위해 `-D`로 시작하는 옵션으로 구분된다.

**설치 위치 옵션**: 설치 경로의 기본 뼈대는 `--prefix` 옵션으로 설정한다. 기본값은 Unix 계열에서는 `/usr/local/pgsql`이다. 이 `PREFIX` 아래에 실행 파일(`--bindir`), 라이브러리(`--libdir`), 헤더 파일(`--includedir`), 설정 파일(`--sysconfdir`), 데이터 파일(`--datadir`) 등이 각각의 하위 디렉터리에 설치된다. 주의할 점은, 이러한 하위 디렉터리들의 상대 위치를 변경하면 설치 후 재배치가 불가능한(non-relocatable) 설치본이 될 수 있다.

공유 설치 위치(예: `/usr/local/include`)에 설치할 때 시스템의 나머지 부분과의 네임스페이스 충돌을 방지하기 위해, `datadir`, `sysconfdir`, `docdir`에는 자동으로 `/postgresql` 문자열이 추가된다. 단, 이미 경로명에 `postgres`나 `pgsql` 문자열이 포함되어 있으면 추가하지 않는다.

**PostgreSQL 기능 옵션**: 특정 기능을 활성화하거나 비활성화하는 옵션이다. 대부분의 옵션(`-Dnls`, `-Dssl`, `-Dicu` 등)은 기본값이 `auto`로, 필요한 소프트웨어가 시스템에 발견되면 자동으로 활성화된다. `enabled`로 명시적으로 요구하거나 `disabled`로 빌드에서 제외할 수 있다. 주요 기능 옵션은 다음과 같다.
| 옵션 | 설명 | 기본값 | 비고 |
| :--- | :--- | :--- | :--- |
| `-Dnls` | Native Language Support (다국어 메시지) | `auto` | Gettext API 필요 |
| `-Dssl` | SSL 암호화 연결 지원 | `auto` | `openssl` 라이브러리만 지원 |
| `-Dicu` | ICU 라이브러리 지원 (콜레이션) | `auto` | ICU4C 패키지 필요 |
| `-Dllvm` | LLVM 기반 JIT 컴파일 지원 | `disabled` | LLVM 라이브러리 필요 |
| `-Dplperl` | PL/Perl 서버 사이드 언어 빌드 | `auto` | |
| `-Dsystemd` | systemd 서비스 알림 지원 | `auto` | `libsystemd` 필요 |
| `-Duuid` | `uuid-ossp` 모듈 빌드 | `none` | `bsd`, `e2fs`, `ossp` 중 선택 |

**Anti-Features 옵션**: 이 옵션들은 특정 라이브러리의 사용을 제어한다. `-Dreadline=auto`(기본값)는 `psql`에서 커맨드 라인 편집과 히스토리 기능을 제공하며 권장된다. `-Dlibedit_preferred=false`(기본값)일 경우, Readline과 libedit이 모두 설치되어 있다면 GPL 라이선스의 Readline을 우선 사용한다. `-Dzlib=auto`는 `pg_dump` 등에서 압축 아카이브를 지원한다.

**빌드 프로세스 세부 옵션**: `--auto-features` 옵션으로 모든 `auto` 상태의 기능을 한꺼번에 `enabled` 또는 `disabled`로 오버라이드할 수 있다. `--backend` 옵션으로 Ninja 이외의 빌드 백엔드를 선택할 수 있으며, 이 경우 `meson compile` 명령으로 빌드한다.

### 주의사항 및 특징
* **업그레이드 시**: 기존 시스템을 업그레이드하는 경우, 반드시 클러스터 업그레이드에 대한 안내가 담긴 문서를 참조해야 한다.
* **테스트 실행 권한**: 회귀 테스트(`meson test`)는 **root가 아닌 일반 사용자**로 실행해야 한다.
* **빌드 자동 감지**: Meson은 소스 트리의 변경을 자동 감지하여 재구성하므로, 여러 빌드 디렉터리를 유지하면서 각각 다른 설정(예: 디버그 빌드, 릴리스 빌드)으로 개발하는 데 유용하다.
* **설치 경로의 유연성**: `--prefix` 하나로 대부분의 설치 위치를 통제할 수 있지만, 하위 디렉터리 경로를 개별적으로 변경하면 설치본의 재배치 가능성이 떨어진다.

### 정리
PostgreSQL의 Meson 빌드 시스템은 `meson setup`으로 구성하고 `ninja`로 빌드하는 간결한 워크플로우를 제공한다. 주요 특징은 소스 변경 자동 감지, 병렬 빌드 최적화, 그리고 `-D` 옵션을 통한 다양한 기능의 모듈화된 활성화이다. 설치 위치는 `--prefix`를 중심으로 구성되며, `auto` 값을 가진 대부분의 기능 옵션은 의존성이 확인되면 자동으로 활성화되어 편의성을 높인다. 이 새로운 빌드 시스템은 특히 다중 구성 개발 환경에서 효율성을 발휘한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/install-meson.html](https://www.postgresql.org/docs/current/install-meson.html)

---
title: "basic_archive — WAL 아카이브 모듈의 설정과 동작 원리"
layout: post
interactive_design: true
categories: ai-notes
type: study-note
date: 2026-11-20 11:05:36 +0900
tags: [postgresql, db]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-11-20
sources:
  - https://www.postgresql.org/docs/current/basic-archive.html
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: `basic_archive`는 완료된 WAL 세그먼트 파일을 지정 디렉터리로 복사하는 예제 아카이브 모듈로, `archive_mode`와 `archive_library` 설정으로 활성화되며 자체 아카이브 모듈 개발의 참조 구현 역할을 한다.

### 개요
PostgreSQL은 WAL 아카이빙을 외부 모듈에 위임할 수 있다. `basic_archive`는 이러한 아카이브 모듈의 예제 구현으로, 완료된 WAL 세그먼트 파일을 지정된 디렉터리로 복사하는 단순한 일을 한다. 실무에서 특별히 유용하지는 않지만, 자신만의 아카이브 모듈을 개발하기 위한 시작점으로 설계되었다.

### basic_archive가 하는 일
이 모듈은 아카이브 모듈의 동작 방식을 보여주는 최소 구현이다. 서버가 WAL 세그먼트 파일 작성을 완료하면, 이 모듈이 해당 파일을 설정된 디렉터리로 복사한다. 동작하려면 두 가지 조건이 충족되어야 한다. 첫째, `archive_library`를 통해 모듈이 로드되어야 하고, 둘째, `archive_mode`가 활성화되어야 한다.

### 설정 파라미터
`basic_archive`가 사용하는 설정 파라미터는 `basic_archive.archive_directory` 하나뿐이다. 이 파라미터는 문자열 타입으로, 서버가 WAL 세그먼트 파일을 복사할 디렉터리를 지정한다. 이 디렉터리는 반드시 이미 존재해야 하며 서버가 생성해 주지 않는다.

기본값은 빈 문자열이다. 빈 문자열이면 WAL 아카이빙이 사실상 중단되지만, `archive_mode`가 활성화된 상태라면 서버는 곧 값이 제공될 것을 기대하며 WAL 세그먼트 파일을 계속 축적한다. 즉, 설정 누락이 즉시 오류로 이어지지 않고 대기 상태로 동작한다.

이 파라미터들은 `postgresql.conf`에 설정해야 한다. 전형적인 사용 예는 다음과 같다.

```ini
# postgresql.conf
archive_mode = 'on'
archive_library = 'basic_archive'
basic_archive.archive_directory = '/path/to/archive/directory'
```



{% raw %}
<figure class="ai-scene"><figcaption>archive_directory 값이 WAL 아카이빙 동작을 어떻게 바꿀까? · 설명용 시각화</figcaption><iframe class="ai-scene-frame" src="/assets/generated/designs/2026-11-20-basic-archive-wal-아카이브-모듈의-설정과-동작-원리-a10081a7a44a6348-1.html" title="archive_directory 값이 WAL 아카이빙 동작을 어떻게 바꿀까?" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy" height="560"></iframe><p class="ai-scene-summary">설명용 설정이다. archive_mode와 archive_library는 고정하고 basic_archive.archive_directory 값만 바꿔 동작을 비교한다. 대상 디렉터리는 이미 존재한다고 가정한다.</p></figure>
{% endraw %}

### 동작 방식과 주의점
서버가 크래시하면 아카이브 디렉터리에 `archtemp` 접두어가 붙은 임시 파일이 남을 수 있다. 크래시 후 서버를 재시작하기 전에 이런 파일을 삭제하는 것이 권장된다. 서버가 실행 중일 때도 삭제가 가능하지만, 진행 중인 아카이빙과 관련이 없는 파일인지 확인해야 한다. 관련이 없는 파일이라면 삭제해도 안전하지만, 그렇지 않을 경우를 대비해 각별한 주의가 필요하다.

### 정리
`basic_archive`는 완료된 WAL 세그먼트를 지정 디렉터리로 복사하는 최소한의 아카이브 모듈 예제다. `archive_mode`와 `archive_library` 설정으로 활성화되며, `basic_archive.archive_directory`로 대상 디렉터리를 지정한다. 빈 문자열 기본값은 아카이빙을 중단시키되 WAL 파일을 축적하는 방식으로 동작하고, 크래시 시 `archtemp` 임시 파일이 남을 수 있으므로 재시작 전 정리가 필요하다. 이 모듈의 가치는 실용성보다는 아카이브 모듈 개발의 참조 구현이라는 점에 있다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.postgresql.org/docs/current/basic-archive.html](https://www.postgresql.org/docs/current/basic-archive.html)

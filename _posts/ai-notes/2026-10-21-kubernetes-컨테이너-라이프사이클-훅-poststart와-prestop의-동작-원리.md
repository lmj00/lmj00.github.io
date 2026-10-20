---
title: "Kubernetes 컨테이너 라이프사이클 훅: PostStart와 PreStop의 동작 원리"
layout: post
interactive_design: true
categories: ai-notes
type: study-note
date: 2026-10-21 08:44:15 +0900
tags: [kubernetes, infra, container]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-10-21
sources:
  - https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/
  - https://kubernetes.io/docs/concepts/containers/container-environment/
  - https://kubernetes.io/docs/tasks/configure-pod-container/attach-handler-lifecycle-event/
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: kubelet이 관리하는 컨테이너가 생성 직후와 종료 직전에 핸들러 코드를 실행할 수 있게 하는 PostStart·PreStop 훅의 실행 시점, 차단 동작, 전달 보장 방식을 정리한다.

### 개요
Kubernetes는 프로그래밍 언어 프레임워크가 컴포넌트 라이프사이클 훅을 제공하는 것(Angular 등)과 유사하게, 컨테이너에도 라이프사이클 훅 프레임워크를 제공한다. 이 훅은 컨테이너가 자신의 관리 라이프사이클에서 발생하는 이벤트를 인지하고, 해당 훅이 실행될 때 핸들러에 구현된 코드를 실행할 수 있게 한다. 훅의 대상은 kubelet이 관리하는 컨테이너이며, 컨테이너가 생성되고 종료되는 과정에 개입할 수 있는 지점을 제공한다.

### 컨테이너에 노출된 훅
컨테이너에 노출된 훅은 **PostStart**, **PreStop**, **StopSignal** 세 가지다.

#### PostStart
PostStart 훅은 컨테이너가 생성된 직후에 실행된다. 컨테이너의 ENTRYPOINT(메인 프로세스)와 동시에 실행되므로, 훅이 메인 프로세스 시작 전·중·후 어느 시점에 실행될지는 보장되지 않는다. 핸들러에는 파라미터가 전달되지 않는다.

훅이 컨테이너 프로세스와 동시에 실행되지만 컨테이너 상태 업데이트를 지연시킬 수 있다는 점에 주의해야 한다. PostStart 훅이 완료되기 전까지 컨테이너는 Running 상태로 전이되지 않을 수 있다.

#### PreStop
PreStop 훅은 API 요청이나 관리 이벤트(예: liveness/startup 프로브 실패, 선점, 리소스 경합)로 인해 컨테이너가 종료되기 직전에 호출된다. 컨테이너가 이미 terminated 또는 completed 상태라면 PreStop 호출은 실패하며, TERM 신호가 전송되기 전에 훅이 완료되어야 한다. 핸들러에는 파라미터가 전달되지 않는다.

Pod의 종료 유예 시간 카운트다운은 PreStop 훅이 실행되기 전에 시작된다. 따라서 핸들러의 결과와 무관하게 컨테이너는 결국 Pod의 종료 유예 시간 안에 종료된다. 또한 preStop 이벤트는 Pod나 Pod 안의 컨테이너가 terminated 될 때만 전송되며, Pod가 completed 되는 경우에는 호출되지 않는다.

#### StopSignal
StopSignal 라이프사이클은 컨테이너가 중지될 때 전송할 중지 신호를 정의하는 데 사용한다. 이 값을 설정하면 컨테이너 이미지에 정의된 STOPSIGNAL 지시어를 덮어쓴다.

### 훅 핸들러 구현과 실행 방식
컨테이너는 훅에 대한 핸들러를 구현하고 등록함으로써 훅에 접근할 수 있다. 핸들러 종류는 세 가지다.

- Exec: 컨테이너의 cgroups와 네임스페이스 안에서 특정 명령(예: `pre-stop.sh`)을 실행한다. 명령이 소비하는 리소스는 컨테이너에 계산된다.
- HTTP: 컨테이너의 특정 엔드포인트에 HTTP 요청을 실행한다.
- Sleep: 지정된 시간 동안 컨테이너를 일시 중지한다.

훅 액션에 따라 실행 주체도 달라진다. `httpGet`, `tcpSocket`(더 이상 사용되지 않음), `sleep`은 kubelet 프로세스가 실행하고, `exec`는 컨테이너 안에서 실행된다.

PostStart 훅 핸들러 호출은 컨테이너가 생성될 때 시작되므로 ENTRYPOINT와 PostStart 훅이 동시에 트리거된다. 따라서 PostStart에 HTTP 훅을 쓰는 것은 일반적으로 의미가 없다. 훅이 실행될 때 컨테이너 프로세스가 완전히 시작되었을 것이라는 보장이 없기 때문이다. PostStart 훅이 너무 오래 걸리거나 멈추면 컨테이너가 running 상태로 전이되지 못할 수 있다.

PreStop 훅은 컨테이너 중지 신호와 비동기적으로 실행되지 않는다. TERM 신호를 보내기 전에 훅이 완료되어야 하며, 훅이 실행 중 멈추면 Pod의 phase는 Terminating 상태로 남아 `terminationGracePeriodSeconds`가 만료된 후에야 Pod가 종료된다. 이 유예 시간은 PreStop 훅 실행과 컨테이너 정상 종료에 걸리는 총 시간에 적용된다. 예를 들어 `terminationGracePeriodSeconds`가 60이고 훅이 55초, 신호 수신 후 정상 종료가 10초가 걸린다면 총 65초가 필요하므로, 컨테이너는 정상 종료되기 전에 강제 종료된다.

PostStart든 PreStop든 훅이 실패하면 컨테이너를 죽인다. 따라서 핸들러는 가능한 한 가볍게 유지해야 하지만, 컨테이너를 중지하기 전에 상태를 저장하는 것처럼 오래 실행되는 명령이 의미 있는 경우도 있다. 실제 예시에서 postStart 핸들러는 `/usr/share` 디렉터리에 message 파일을 쓰고, preStop 핸들러는 `nginx -s quit`로 nginx를 정상 종료한 뒤 `killall -0 nginx`로 프로세스가 끝날 때까지 대기한다.

![diagram](/assets/diagrams/2026-10-21-kubernetes-컨테이너-라이프사이클-훅-poststart와-prestop의-동작-원리-1-dc62f6c8a2bf231a.svg)



{% raw %}
<figure class="ai-scene"><figcaption>PreStop 훅이 유예 시간을 넘기면 정상 종료 전 강제 종료된다 · 설명용 시각화</figcaption><iframe class="ai-scene-frame" src="/assets/generated/designs/2026-10-21-kubernetes-컨테이너-라이프사이클-훅-poststart와-prestop의-동작-원리-569bc49c73f20a29-1.html" title="PreStop 훅이 유예 시간을 넘기면 정상 종료 전 강제 종료된다" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy" height="560"></iframe><p class="ai-scene-summary">고정 입력: 유예 60s(terminationGracePeriodSeconds)와 정상 종료 시도 10s. 훅 20s는 설명용 수치, 훅 55s는 문서 예시. 훅+정상 종료 합계가 60s를 넘으면 정상 종료 전 강제 종료된다.</p></figure>
{% endraw %}

### 훅 전달 보장과 디버깅
훅 전달은 의도상 **at least once**다. 즉 PostStart나 PreStop 같은 특정 이벤트에 대해 훅이 여러 번 호출될 수 있으며, 이를 올바르게 처리하는 것은 훅 구현의 책임이다.

일반적으로는 단일 전달만 이루어진다. 예를 들어 HTTP 훅 수신자가 다운되어 트래픽을 받지 못해도 재전송 시도는 없다. 다만 드물게 이중 전달이 발생할 수 있는데, kubelet이 훅 전송 중에 재시작되면 kubelet이 복귀한 후 훅이 다시 전송될 수 있다.

훅 핸들러의 로그는 Pod 이벤트에 노출되지 않는다. 핸들러가 실패하면 이벤트를 브로드캐스트하는데, PostStart는 `FailedPostStartHook`, PreStop은 `FailedPreStopHook` 이벤트다. 예를 들어 postStart 명령을 `badcommand`로 바꾸면 `kubectl describe pod`에서 `FailedPostStartHook` 경고 이벤트와 함께 명령이 `$PATH`에 없어 실패했다는 OCI 런타임 오류 메시지가 나타나고, 이어서 Killing 이벤트와 BackOff로 실패한 컨테이너를 재시작하는 과정이 이어진다.

### 정리
Kubernetes의 컨테이너 라이프사이클 훅은 생성 직후(PostStart)와 종료 직전(PreStop)이라는 두 지점에서 컨테이너가 자신의 수명 주기 이벤트에 반응할 수 있게 한다. PostStart는 ENTRYPOINT와 동시에 실행되어 Running 전이를 지연시킬 수 있고, PreStop은 TERM 신호 전에 완료되어야 하며, 훅 실행과 정상 종료 시간의 합이 `terminationGracePeriodSeconds`를 넘으면 컨테이너는 강제 종료된다. 훅 전달은 at least once로 설계되어 구현이 중복 호출을 처리해야 하고, 실패는 `FailedPostStartHook`·`FailedPreStopHook` 이벤트로만 드러나므로 핸들러는 가볍게 유지하는 것이 핵심이다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/](https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/)
> - [https://kubernetes.io/docs/concepts/containers/container-environment/](https://kubernetes.io/docs/concepts/containers/container-environment/)
> - [https://kubernetes.io/docs/tasks/configure-pod-container/attach-handler-lifecycle-event/](https://kubernetes.io/docs/tasks/configure-pod-container/attach-handler-lifecycle-event/)

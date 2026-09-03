---
title: "Kubernetes Volume과 hostPath — 파드가 호스트 파일시스템을 바라보는 방식"
layout: post
categories: ai-notes
type: study-note
date: 2026-09-04 08:07:01 +0900
tags: [kubernetes, infra, container]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-09-04
sources:
  - https://kubernetes.io/docs/concepts/storage/volumes/
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: 파드의 컨테이너는 컨테이너 이미지의 루트 파일시스템 위에 볼륨을 마운트해 데이터를 공유하며, hostPath는 그중 호스트 노드의 디렉터리나 파일을 직접 노출하는 강력하지만 위험한 수단이다.

### 개요
Kubernetes의 Volume은 파드 안 컨테이너가 파일시스템을 통해 데이터에 접근하고 공유하는 방법을 제공한다. 컨테이너의 온디스크 파일은 휘발성이어서 컨테이너가 크래시하거나 중지되면 상태가 저장되지 않고 수명 동안 생성·수정된 모든 파일이 사라진다. 또 한 파드 안의 여러 컨테이너가 파일을 공유하려면 공유 파일시스템을 구성하기 어렵다. Volume 추상화는 이 두 문제를 함께 해결하기 위한 개념이다.

### Volume이 필요한 이유
컨테이너의 온디스크 파일은 본질적으로 임시적이다. 컨테이너가 크래시하면 kubelet이 컨테이너를 깨끗한 상태로 재시작하므로, 비단순한 애플리케이션은 파일 유실 문제를 겪는다. 동시에 한 파드 안에서 여러 컨테이너가 파일을 공유해야 하는 경우에도 공유 파일시스템을 구성하고 접근하는 일은 까다롭다. Volume은 이 두 문제를 해결하기 위한 추상화다.

### Volume의 동작 원리
Kubernetes는 여러 종류의 볼륨을 지원하며, 파드는 여러 볼륨 타입을 동시에 사용할 수 있다. 임시(ephemeral) 볼륨 타입의 수명은 특정 파드에 묶여 있지만, 영구(persistent) 볼륨은 개별 파드의 수명을 넘어 존재한다. 파드가 사라지면 Kubernetes는 임시 볼륨을 파괴하지만 영구 볼륨은 파괴하지 않는다. 어떤 종류의 볼륨이든 파드 안에서 데이터는 컨테이너 재시작을 넘어 보존된다.

핵심적으로 볼륨은 디렉터리다. 그 디렉터리가 어떻게 생겨나고, 어떤 매체가 뒷받침하며, 어떤 내용을 담는지는 사용하는 볼륨 타입이 결정한다. 볼륨을 사용하려면 `.spec.volumes`에 파드가 제공할 볼륨을 지정하고, `.spec.containers[*].volumeMounts`에서 각 컨테이너에 어디에 마운트할지 선언한다.

파드가 시작되면 컨테이너의 프로세스는 컨테이너 이미지의 초기 내용에 볼륨이 마운트된 파일시스템 뷰를 보게 된다. 루트 파일시스템은 처음에 컨테이너 이미지의 내용과 일치하며, 볼륨은 컨테이너 파일시스템 안의 지정된 경로에 마운트된다. 각 컨테이너는 사용하는 볼륨을 어디에 마운트할지 독립적으로 지정해야 한다. 볼륨은 다른 볼륨 안에 마운트될 수 없고, 다른 볼륨의 무엇에 대한 하드 링크도 담을 수 없다.

### hostPath: 호스트 파일시스템을 직접 마운트
hostPath 볼륨은 호스트 노드의 파일시스템에서 파일이나 디렉터리를 파드로 마운트한다. 대부분의 파드가 필요로 하지는 않지만, 특정 애플리케이션에는 강력한 탈출구가 된다. 다만 문서는 이 타입이 많은 보안 위험을 지닌다고 경고하며, 피할 수 있다면 사용하지 말고 대신 local PersistentVolume을 정의하라고 권고한다.

hostPath를 사용할 만한 경우는 노드 수준의 시스템 컴포넌트에 접근해야 하는 컨테이너를 실행할 때다. 예를 들어 시스템 로그를 중앙 위치로 전송하는 컨테이너가 `/var/log`를 읽기 전용으로 마운트해 접근하는 경우, 또는 일반 파드와 달리 ConfigMap에 접근할 수 없는 static Pod에 호스트에 저장된 설정 파일을 읽기 전용으로 제공하는 경우가 있다.

#### hostPath의 보안 위험
호스트 파일시스템에 대한 접근은 kubelet 같은 특권 시스템 자격 증명이나 컨테이너 런타임 소켓 같은 특권 API를 노출할 수 있으며, 이는 컨테이너 탈출이나 클러스터의 다른 부분 공격에 악용될 수 있다. admission-time 검증으로 노드의 특정 디렉터리에 대한 접근을 제한하더라도, 그 hostPath 마운트가 읽기 전용임을 추가로 강제하지 않으면 제한은 효과가 없다. 신뢰할 수 없는 파드가 어떤 호스트 경로를 읽기-쓰기로 마운트할 수 있다면 그 컨테이너는 호스트 마운트를 무력화할 수 있다.

또한 동일한 구성의 파드(예: PodTemplate에서 생성된 파드)라도 노드마다 파일이 다르므로 노드에 따라 다르게 동작할 수 있다. hostPath 볼륨 사용은 임시 스토리지 사용으로 간주되지 않으므로, 과도한 디스크 사용이 노드 디스크 압박으로 이어지지 않도록 직접 모니터링해야 한다.

#### type 필드
hostPath 볼륨은 필수 `path` 속성 외에 선택적으로 `type`을 지정할 수 있다. `type` 값에 따라 마운트 전 검사가 달라진다.

| type 값 | 동작 |
| --- | --- |
| `""` (기본값) | 하위 호환용. 마운트 전 아무 검사도 수행하지 않는다 |
| `DirectoryOrCreate` | 경로에 아무것도 없으면 0755 권한, kubelet과 같은 그룹·소유권으로 빈 디렉터리를 생성한다 |
| `Directory` | 경로에 디렉터리가 반드시 존재해야 한다 |
| `FileOrCreate` | 경로에 아무것도 없으면 0644 권한, kubelet과 같은 그룹·소유권으로 빈 파일을 생성한다 |
| `File` | 경로에 파일이 반드시 존재해야 한다 |
| `Socket` | 경로에 UNIX 소켓이 존재해야 한다 |
| `CharDevice` | (Linux 노드만) 경로에 문자 디바이스가 존재해야 한다 |
| `BlockDevice` | (Linux 노드만) 경로에 블록 디바이스가 존재해야 한다 |

`FileOrCreate` 모드는 파일의 부모 디렉터리를 만들지 않는다. 마운트할 파일의 부모 디렉터리가 존재하지 않으면 파드가 시작에 실패하므로, 디렉터리와 파일을 분리해 마운트하는 방식이 권장된다. 호스트에 생성된 파일이나 디렉터리가 root만 접근 가능하다면, 특권 컨테이너에서 root로 프로세스를 실행하거나 호스트에서 파일 권한을 수정해야 읽거나 쓸 수 있다.

#### hostPath 예제
다음 매니페스트는 호스트의 `/data/foo`를 컨테이너 안의 `/foo`에 읽기 전용으로 마운트한다.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-example-linux
spec:
  os:
    name: linux
  nodeSelector:
    kubernetes.io/os: linux
  containers:
  - name: example-container
    image: registry.k8s.io/test-webserver
    volumeMounts:
    - mountPath: /foo
      name: example-volume
      readOnly: true
  volumes:
  - name: example-volume
    hostPath:
      path: /data/foo
      type: Directory
```

볼륨 정의에서 `hostPath.path`로 호스트의 `/data/foo`를 가리키고 `type: Directory`를 지정해 이미 존재하는 디렉터리만 마운트하도록 한다. 컨테이너 쪽에서는 `volumeMounts`로 `example-volume`을 `/foo`에 읽기 전용으로 연결한다. 이 흐름을 그림으로 나타내면 다음과 같다.

![diagram](/assets/diagrams/2026-09-04-kubernetes-volume과-hostpath-파드가-호스트-파일시스템을-바라보는-방식-1.svg)

### 정리
Kubernetes Volume은 컨테이너의 휘발성 파일시스템 문제와 다중 컨테이너 간 파일 공유 문제를 해결하는 추상화로, 파드 스펙의 `.spec.volumes`와 컨테이너의 `volumeMounts` 선언을 통해 컨테이너 이미지 위에 디렉터리를 마운트한다. hostPath는 그중 호스트 노드의 파일이나 디렉터리를 직접 노출하는 타입으로, 노드 수준 컴포넌트 접근이나 static Pod 설정 제공 같은 특수한 경우에 유용하다. 다만 호스트 파일시스템 접근은 특권 자격 증명 노출과 컨테이너 탈출 위험을 수반하므로, 피할 수 있다면 local PersistentVolume 같은 대안을 사용하는 것이 안전하다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://kubernetes.io/docs/concepts/storage/volumes/](https://kubernetes.io/docs/concepts/storage/volumes/)

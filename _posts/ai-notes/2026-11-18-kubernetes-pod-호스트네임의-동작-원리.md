---
title: "Kubernetes Pod 호스트네임의 동작 원리"
layout: post
interactive_design: true
categories: ai-notes
type: study-note
date: 2026-11-18 11:50:24 +0900
tags: [kubernetes, infra, container]
generated_by: "openrouter:deepseek/deepseek-v4-flash-0731"
generated_at: 2026-11-18
sources:
  - https://kubernetes.io/docs/concepts/workloads/pods/pod-hostname/
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

> 한 줄 요약: Pod 내부의 호스트네임과 FQDN은 `metadata.name`에서 파생되며, `hostname`·`subdomain`·`setHostnameAsFQDN`·`hostnameOverride` 필드가 각각 다른 방식으로 이 값을 바꾼다.

### 개요
Pod 내부에서 관찰되는 호스트네임은 단순한 컨테이너 설정이 아니라 Pod의 메타데이터와 spec 필드로부터 파생되는 값이다. Kubernetes는 기본적으로 `metadata.name`에서 호스트네임을 만들고, `spec.hostname`, `spec.subdomain`, `setHostnameAsFQDN`, `hostnameOverride` 같은 필드로 이 동작을 조정한다. 각 필드가 호스트네임과 FQDN(정규화된 도메인 이름), 그리고 클러스터 DNS의 A/AAAA 레코드에 미치는 영향이 서로 다르므로 이를 구분해서 이해해야 한다.

### 호스트네임과 FQDN의 기본 구성
Pod가 생성되면 Pod 내부에서 관찰되는 호스트네임은 `metadata.name` 값에서 파생된다. 호스트네임과 그에 대응하는 FQDN 모두 Pod의 관점에서 `metadata.name` 값으로 설정된다. 예를 들어 `metadata.name`이 `busybox-1`인 Pod는 내부에서 호스트네임과 FQDN이 모두 `busybox-1`로 보인다.

Pod spec의 선택적 `hostname` 필드가 설정되면 이 값이 `metadata.name`보다 우선해서 Pod 내부에서 관찰되는 호스트네임이 된다. `spec.hostname`을 `my-host`로 설정한 Pod의 호스트네임은 `my-host`가 된다. 선택적 `subdomain` 필드는 Pod가 자신의 네임스페이스 안에서 특정 서브도메인에 속함을 나타낸다. `spec.hostname`이 `foo`, `spec.subdomain`이 `bar`, 네임스페이스가 `my-namespace`라면 호스트네임은 `foo`가 되고 FQDN은 `foo.bar.my-namespace.svc.cluster-domain.example`이 된다(Pod 내부 관찰 기준).

FQDN은 `spec.hostname`(지정되지 않았다면 `metadata.name`), `spec.subdomain`, 네임스페이스 이름, 클러스터 도메인 접미사가 결합된 형태다. `hostname`과 `subdomain`이 모두 설정되면 클러스터의 DNS 서버는 이 필드들을 바탕으로 A 및/또는 AAAA 레코드를 생성한다.

### `setHostnameAsFQDN`: FQDN을 호스트네임으로 기록
이 기능은 Kubernetes v1.22부터 Stable이다. Pod가 FQDN을 가지도록 구성된 경우 기본적으로 호스트네임은 짧은 호스트네임(short hostname)이다. 예를 들어 FQDN이 `busybox-1.busybox-subdomain.my-namespace.svc.cluster-domain.example`인 Pod에서 `hostname` 명령은 `busybox-1`을 반환하고, `hostname --fqdn` 명령은 FQDN을 반환한다.

Pod spec에 `setHostnameAsFQDN: true`와 `subdomain` 필드가 모두 설정되면 kubelet이 Pod의 FQDN을 해당 Pod의 호스트네임으로 기록한다. 이 경우 `hostname`과 `hostname --fqdn` 모두 Pod의 FQDN을 반환한다.

여기에는 중요한 제약이 있다. Linux에서 커널의 hostname 필드(`struct utsname`의 `nodename` 필드)는 64자로 제한된다. 이 기능을 활성화했는데 FQDN이 64자를 넘으면 Pod는 시작에 실패하고, `Pending` 상태(`kubectl`로는 `ContainerCreating`으로 보임)에 머물며 "Failed to construct FQDN from Pod hostname and cluster domain" 같은 오류 이벤트를 생성한다. 따라서 이 필드를 사용할 때는 `metadata.name`(또는 `spec.hostname`)과 `spec.subdomain`의 길이를 합쳐 FQDN이 64자를 넘지 않도록 해야 한다.

### `hostnameOverride`: 무조건적 오버라이드
`hostnameOverride`는 v1.34에서 처음 제공되었고 v1.37부터 Stable이며 기본으로 활성화되어 있다. Pod spec에 `hostnameOverride` 값을 설정하면 kubelet이 Pod의 호스트네임과 FQDN을 모두 그 값으로 무조건 설정한다. 이 필드는 64자 길이 제한이 있고 RFC 1123에 정의된 DNS 서브도메인 이름 표준을 따라야 한다.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: busybox-2-busybox-example-domain
spec:
  hostnameOverride: busybox-2.busybox.example.domain
  containers:
  - image: busybox:1.28
    command:
    - sleep
    - "3600"
    name: busybox
```

`hostnameOverride`는 Pod 내부의 호스트네임에만 영향을 주며 클러스터 DNS 서버의 A 또는 AAAA 레코드에는 영향을 주지 않는다. `hostnameOverride`가 `hostname`·`subdomain` 필드와 함께 설정되면 Pod 내부의 호스트네임은 `hostnameOverride` 값으로 덮어써지지만, DNS의 A 및/또는 AAAA 레코드는 여전히 `hostname`과 `subdomain` 필드를 바탕으로 생성된다. 또한 `hostnameOverride`가 설정된 경우 `hostNetwork`와 `setHostnameAsFQDN` 필드를 동시에 설정할 수 없으며, API 서버는 이 조합을 포함한 생성 요청을 명시적으로 거부한다. `hostnameOverride`가 다른 필드(`hostname`, `subdomain`, `setHostnameAsFQDN`, `hostNetwork`)와 조합될 때의 동작은 KEP-4762 설계 세부사항의 표에 정리되어 있다.



{% raw %}
<figure class="ai-scene"><figcaption>hostnameOverride는 무엇을 덮어쓰고 무엇을 남길까? · 설명용 시각화</figcaption><iframe class="ai-scene-frame" src="/assets/generated/designs/2026-11-18-kubernetes-pod-호스트네임의-동작-원리-a1d70b915c26b126-1.html" title="hostnameOverride는 무엇을 덮어쓰고 무엇을 남길까?" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy" height="560"></iframe><p class="ai-scene-summary">설명용 값: hostname=foo, subdomain=bar, namespace=my-namespace, hostnameOverride=my-host.example. hostnameOverride는 내부 호스트네임·FQDN만 덮어쓰고 DNS 레코드는 hostname·subdomain 기반으로 남는다.</p></figure>
{% endraw %}

### 설정별 동작 비교
지금까지 설명한 네 가지 설정이 호스트네임, FQDN, DNS 레코드에 미치는 영향을 같은 기준으로 비교하면 다음과 같다.

| 설정 | Pod 내부 호스트네임 | FQDN | 클러스터 DNS A/AAAA 레코드 |
|---|---|---|---|
| 기본값 | `metadata.name` | `metadata.name` | — |
| `hostname` + `subdomain` | `spec.hostname` | `spec.hostname`·`spec.subdomain`·네임스페이스·클러스터 도메인 접미사의 결합 | `hostname`·`subdomain` 필드를 바탕으로 생성 |
| `setHostnameAsFQDN: true` (+ `subdomain`) | FQDN 전체 | FQDN 전체 | — |
| `hostnameOverride` | `hostnameOverride` 값 | `hostnameOverride` 값 | `hostname`·`subdomain` 필드를 바탕으로 생성(영향 없음) |

기본 설정과 `setHostnameAsFQDN` 사용 시 DNS 레코드 동작은 문서에서 별도로 명시하지 않는다.

### 정리
Pod 내부의 호스트네임은 기본적으로 `metadata.name`에서 파생되며, `spec.hostname`이 설정되면 그것이 우선한다. FQDN은 호스트네임(또는 `metadata.name`)과 `subdomain`, 네임스페이스, 클러스터 도메인 접미사가 결합된 형태이며, `setHostnameAsFQDN`을 켜면 kubelet이 전체 FQDN을 호스트네임으로 기록한다. `hostnameOverride`는 호스트네임과 FQDN을 모두 강제로 덮어쓰지만 DNS 레코드에는 영향을 주지 않으므로, 64자 길이 제한과 필드 조합 제약을 함께 고려해야 한다.

---
> 🤖 작성 모델: `deepseek/deepseek-v4-flash-0731` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://kubernetes.io/docs/concepts/workloads/pods/pod-hostname/](https://kubernetes.io/docs/concepts/workloads/pods/pod-hostname/)

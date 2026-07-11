---
title: "RabbitMQ의 OAuth 2.0 인증 백엔드: 개념과 동작 방식"
layout: post
categories: ai-notes
type: study-note
date: 2026-07-12 06:50:54 +0900
tags: [rabbitmq]
generated_by: "openrouter:deepseek/deepseek-v3.2"
generated_at: 2026-07-12
sources:
  - https://www.rabbitmq.com/docs/oauth2
---

> 🤖 이 글은 공식문서를 근거로 **AI가 자동 생성**한 학습 노트입니다.

### 개요
RabbitMQ의 **OAuth 2.0 Authentication Backend** 플러그인은 클라이언트 애플리케이션과 사용자가 JWT로 인코딩된 OAuth 2.0 액세스 토큰을 사용하여 인증 및 권한 부여를 수행할 수 있게 해준다. 이는 기존의 내부 자격 증명 관리 방식을 외부 신원 공급자(IdP)에 위임하는 방식으로, 중앙화된 권한 관리와 보안 강화를 가능하게 한다.

### OAuth 2.0 백엔드의 핵심 동작 원리
이 플러그인은 OAuth 2.0 공급자와 실시간으로 통신하여 사용자를 인증하지 않는다. 대신, 클라이언트가 제공한 **액세스 토큰을 디코딩하고 검증**하여 그 안에 포함된 **스코프(권한)** 를 기반으로 사용자의 접근을 허가한다.

인증 흐름은 다음과 같은 순서로 진행된다.
![diagram](/assets/diagrams/2026-07-12-rabbitmq의-oauth-2-0-인증-백엔드-개념과-동작-방식-1.svg)

**토큰 검증**은 다음과 같은 조건을 충족해야 한다.
*   **디지털 서명**이 되어 있어야 한다. 서명 검증을 위한 키를 RabbitMQ가 획득할 수 있어야 한다.
*   토큰의 `aud`(audience) 클레임 값 중 하나가 RabbitMQ에 구성된 `resource_server_id`와 일치해야 한다. (이 검증은 `auth_oauth2.verify_aud = false`로 비활성화할 수 있지만 권장되지 않는다.)
*   토큰 내 스코프는 `resource_server_id` 값을 접두사로 포함하는 **인식 가능한 RabbitMQ 스코프**이거나, 매핑 설정을 통해 변환 가능해야 한다.

### 서명 키 획득 방식
RabbitMQ가 토큰 서명을 검증하기 위한 공개 키를 얻는 방법은 세 가지가 있다.

| 방식 | 구성 키 | 설명 | 사용 사례 |
| :--- | :--- | :--- | :--- |
| **Issuer URL** (권장) | `auth_oauth2.issuer` | OpenID Connect Discovery 프로토콜을 통해 자동으로 JWKS 엔드포인트를 발견하고 서명 키를 다운로드한다. | 대부분의 OpenID Connect 호환 공급자(Keycloak, Auth0, Azure AD, Okta 등)와 함께 사용. |
| **JWKS 엔드포인트 직접 지정** | `auth_oauth2.jwks_uri` | 서명 키를 반환하는 JWKS 엔드포인트 URL을 직접 구성한다. | 공급자가 Discovery를 지원하지 않거나, 발견된 엔드포인트를 재정의해야 할 때 사용. |
| **정적 서명 키** | `auth_oauth2.signing_keys` | 서명 키를 로컬 파일로 직접 구성한다. | 네트워크가 차단된 환경이나 대칭 키를 사용할 때 유용. |

Issuer URL이나 JWKS 엔드포인트를 사용하면, RabbitMQ는 필요할 때(새로운 서명 키를 발견했을 때) HTTP 요청을 통해 키를 한 번 다운로드한다. 서명 키 회전 시 새로운 키에 대한 다운로드가 다시 트리거된다.

### 스코프와 권한의 변환
토큰 내부의 스코프는 RabbitMQ가 이해할 수 있는 **권한(퍼미션)** 으로 변환되어야 한다. 이 변환 과정은 몇 가지 계층적 구성을 통해 이루어진다.

1.  **스코프 추출 위치 설정**: 기본적으로 토큰의 `scope` 클레임에서 스코프를 읽는다. `auth_oauth2.additional_scopes_key`를 설정하면 `scope` 외에 다른 클레임(예: `extra_scope`, `realm_access.roles`)에서도 스코프를 추가로 읽어올 수 있다. 값은 공백으로 구분된 문자열이나 JSON 리스트 형식이 될 수 있다.
2.  **인식 가능한 RabbitMQ 스코프 패턴**: RabbitMQ가 기본적으로 인식하는 스코프는 `{resource_server_id}.{권한유형}:{대상}` 형식이다. 예를 들어 `resource_server_id`가 `rabbitmq`라면, `rabbitmq.tag:administrator`(관리자 태그 부여), `rabbitmq.configure:*/*`(모든 vhost의 모든 리소스에 configure 권한 부여)와 같은 형태다.
3.  **스코프 접두사 사용자 정의**: 스코프가 다른 접두사로 시작한다면 `auth_oauth2.scope_prefix`로 재정의할 수 있다. 예를 들어 `api://tag:administrator` 같은 스코프를 사용하려면 `scope_prefix = api://`로 설정한다.
4.  **스코프 별칭을 통한 매핑**: 토큰의 스코프가 RabbitMQ 형식이 아닌 경우(예: `admin`, `developer`), `auth_oauth2.scope_aliases`를 사용해 매핑해야 한다. 이 설정은 사용자 정의 스코프를 하나 이상의 RabbitMQ 스코프로 변환한다.
    ```ini
    auth_oauth2.scope_aliases.admin = rabbitmq.tag:administrator rabbitmq.read:*/
    ```

### 관리 UI에서의 OAuth 2.0 활성화
메시징 프로토콜(AMQP, MQTT 등)을 통한 연결 인증 외에, **RabbitMQ 관리 UI**에서도 OAuth 2.0 로그인을 활성화할 수 있다. 이를 **서비스 공급자 주도 로그온(Service Provider initiated logon)** 이라고 한다.

필수 구성은 다음과 같다.
*   `management.oauth_enabled = true`: 관리 UI에 OAuth 2.0 인증을 활성화한다.
*   `management.oauth_client_id = <클라이언트_ID>`: 신원 공급자에 등록된 퍼블릭 클라이언트의 ID를 지정한다. (UAA는 추가로 `client_secret`이 필요할 수 있음)
*   `management.oauth_scopes = openid profile rabbitmq.tag:management`: 관리 UI가 토큰을 요청할 때 포함시킬 스코프 목록을 설정한다. `openid`와 `profile`은 일반적으로 필수이며, 뒤이어 RabbitMQ 권한 스코프를 추가한다.

기본적으로 OAuth 2.0이 관리 UI에서 활성화되면 **기본 인증(Basic Auth)은 비활성화된다.** `management.oauth_disable_basic_auth = false`를 설정하면 두 가지 인증 방식을 모두 사용할 수 있다.

### 고려 사항 및 주의점
*   **HTTPS 필수**: `auth_oauth2.issuer`나 `auth_oauth2.jwks_uri`는 반드시 HTTPS URL이어야 한다. 자체 서명된 인증서를 사용한다면 `auth_oauth2.https.cacertfile`로 CA 인증서를 지정해야 한다.
*   **사용자 이름 클레임**: 로깅과 관리 UI 표시를 위해 RabbitMQ는 토큰에서 사용자 이름을 추출한다. 기본 순서는 `sub`, `client_id`이다. `auth_oauth2.preferred_username_claims`로 다른 클레임(예: `user_name`, `preferred_username`)을 사용하도록 우선순위를 정의할 수 있다.
*   **다중 공급자/리소스 서버**: 여러 OAuth 2.0 공급자를 지원하거나, 여러 리소스 서버 ID를 사용하는 고급 구성도 가능하다.

### 정리
*   RabbitMQ OAuth 2.0 백엔드는 클라이언트가 제공한 JWT 토큰의 서명과 클레임을 검증하여 인증 및 권한을 부여하는 **토큰 검증자** 역할을 한다.
*   토큰의 `aud` 클레임과 `scope` 클레임이 각각 `resource_server_id` 및 인식 가능한 RabbitMQ 권한 패턴과 일치하거나 매핑되어야 한다.
*   서명 키 획득에는 Issuer URL(권장), JWKS 엔드포인트 직접 지정, 정적 키 파일 방식이 있으며, OpenID Connect 호환 공급자와의 연동이 가장 일반적이다.
*   관리 UI에서의 OAuth 2.0 로그인을 별도로 활성화할 수 있으며, 이 경우 기본 인증이 대체된다.

---
> 🤖 작성 모델: `deepseek/deepseek-v3.2` (OpenRouter)
> 
> 참고한 공식문서:
> - [https://www.rabbitmq.com/docs/oauth2](https://www.rabbitmq.com/docs/oauth2)

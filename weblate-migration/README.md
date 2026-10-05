# Zanata에서 Weblate로의 마이그레이션 도구

이 폴더는 번역 프로젝트를 Zanata에서 Weblate로 마이그레이션하는 도구를
제공합니다.

> **참고:** 현재 이 도구는 horizon 및 plugin 프로젝트에서 동작합니다.

## 배경

OpenStack I18n 팀은 그동안 [Zanata](https://github.com/zanata/zanata-platform)를
번역 플랫폼으로 사용해왔으나, 2018년 8월부터 개발과 릴리스가 중단되었습니다.
지속적인 번역 관리와 OpenStack 국제화 워크플로우 개선을 위해, OpenStack I18n
SIG는 Zanata 프로젝트를 Weblate로 마이그레이션하고 있습니다.

## 목표

* 기존 번역 구조와 형식을 최대한 그대로 보존

## 마이그레이션 워크플로우

1. 작업 공간(workspace)을 설정합니다.
2. 클론한 프로젝트 저장소에서 POT 파일을 생성합니다.
3. `zanata.xml`을 만들고 Zanata에서 번역(PO 파일)을 export합니다.
4. Weblate 프로젝트, 카테고리, 컴포넌트를 생성합니다.
5. 번역을 생성하고 로케일별로 번역 파일을 업로드합니다.

## 사용 방법

1. 저장소를 클론합니다.
2. 마이그레이션 스크립트를 실행합니다.

* 프로젝트 단일 마이그레이션:

```bash
./migration_resources.sh <project_name> <version> <workspace_name>
```

인자:

* project_name: 마이그레이션할 OpenStack 프로젝트 이름.
* version: 프로젝트 버전. 기본값은 "master"입니다.
  예: stable-2025.1
* workspace_name: 마이그레이션 작업 공간 폴더 이름.
  홈 디렉터리 아래에 생성됩니다. 기본값은 "workspace"입니다.

* 프로젝트 그룹 마이그레이션:

```bash
./migration_projects.sh <project_list.txt> <version_list.txt>
```

인자:

* project_list.txt: 마이그레이션할 프로젝트 목록이 담긴 텍스트 파일.
  한 줄에 프로젝트 이름 하나씩 적습니다.

  예시:

  ```text
  designate-dashboard
  freezer-web-ui
  ```

* version_list.txt: 마이그레이션할 버전 목록이 담긴 텍스트 파일.
  한 줄에 버전 이름 하나씩 적습니다.
  버전 이름은 프로젝트 저장소의 브랜치 이름과 같아야 합니다.

  예시:

  ```text
  master
  stable/2025.2
  ```

## 로그

로그 폴더(/log)는 현재 저장소 디렉터리 안에 생성됩니다.

* project.{timestamp}.log: 프로젝트 마이그레이션 로그 파일.
* error.{timestamp}.log: 에러만 모은 로그 파일.

타임스탬프는 마이그레이션 시작 시각이며, 형식은 HHMMSS입니다.

```text
├── log/
│   └── <project_name>/
│       └── project.{timestamp}.log
│       └── error.{timestamp}.log
```

## 폴더 및 파일 구조

```text
├── common/
├── 01-setup-env/
├── 02-prepare-translations/
├── 03-prepare-component-name/
├── 04-prepare-weblate-components/
├── 05-test-accuracy/
├── migration_resources.sh
└── migration_projects.sh
```

* common/: 여러 마이그레이션 단계에서 공통으로 쓰는 유틸리티
  (Weblate API 호출, PO/POT 경로 처리, 컬러 stage 출력).
* 01-setup-env/: 가상환경을 생성하고, 의존성을 설치하고, 마이그레이션
  작업을 위한 workspace 폴더를 준비합니다.
* 02-prepare-translations/: 프로젝트를 클론하고, POT 파일을 생성하고,
  Zanata에서 번역(PO 파일)을 export합니다.
* 03-prepare-component-name/: 번역된 각 모듈에 대해 Weblate 컴포넌트
  이름을 감지합니다.
* 04-prepare-weblate-components/: Weblate 프로젝트, 카테고리, 컴포넌트를
  생성하고 번역을 업로드합니다.
* 05-test-accuracy/: 마이그레이션된 번역을 원본과 비교해 검증합니다.
* migration_resources.sh / migration_projects.sh: 프로젝트 하나 또는
  프로젝트 그룹에 대해 위 단계들을 순서대로 실행하는 진입점입니다.

로그 형식은 다음과 같습니다.

```text
// project | category | component | locale | message
horizon | stable/2025.2 | openstack-dashboard-django | mai | [INFO] Testing locale: mai
horizon | stable/2025.2 | openstack-dashboard-django | mai | [INFO] Step 1/2: Check the sentence count...
horizon | stable/2025.2 | openstack-dashboard-django | mai | [INFO] ✓ Count matched(translated/total): 73/177
horizon | stable/2025.2 | openstack-dashboard-django | mai | [INFO] Step 2/2: Check the sentence detail...
horizon | stable/2025.2 | openstack-dashboard-django | mai | [INFO] ✓ Sentence detail matched: 177 entries
```

`component`/`locale`는 아직 컴포넌트/로케일이 정해지지 않은 단계
(클론, POT 생성 등)의 로그에서는 `-`로 표시됩니다.

> **참고:** 현재 이 도구는 주로 번역 리소스 마이그레이션에 초점을
> 맞추고 있으며, 실제 리소스 마이그레이션 과정은 각 단계가 제대로
> 수행되었는지 주의 깊게 확인해야 합니다.

## Workspace 구조

기본적으로 마이그레이션 workspace는 홈 디렉터리에 아래와 같은 폴더
구조로 설치됩니다.

> **참고:** `01-setup-env/setup.sh`에서 WORK_DIR을 직접 설정하면
> 기본 디렉터리를 변경할 수 있습니다.

* .venv/: 마이그레이션 의존성이 담긴 파이썬 가상환경
* projects/: 마이그레이션 작업 공간
  * \<project_name>/: 프로젝트별 작업 공간
    * \<cloned_project_name>/: 클론된 프로젝트 저장소
    * pot/: 각 컴포넌트의 POT 파일
    * translations/: Zanata에서 export한 번역

디렉터리 레이아웃:

```text
<workspace_name>/
├── .venv/
└── projects/
    └── <project_name>/
        ├── <cloned_project_name>/
        ├── pot/
        └── translations/
```

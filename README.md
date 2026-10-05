# i18n-zanata-to-weblate-migration

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Issues](https://img.shields.io/github/issues/openstack-kr/i18n-zanata-to-weblate-migration)](https://github.com/openstack-kr/i18n-zanata-to-weblate-migration/issues)
[![Last Commit](https://img.shields.io/github/last-commit/openstack-kr/i18n-zanata-to-weblate-migration)](https://github.com/openstack-kr/i18n-zanata-to-weblate-migration/commits)

Repos for the scripts and related data / doc to demonstrate end-to-end
migration steps from OpenStack Zanata to Weblate.

OpenStack I18n(국제화) SIG이 [Zanata](https://github.com/zanata/zanata-platform)
(2018년 8월 개발 중단)에 있던 번역 리소스를 [Weblate](https://weblate.org)로
옮기기 위해 쓰는 도구 모음입니다. 기존 번역 내용과 형식(플루럴, fuzzy 등)을
최대한 보존하는 것을 목표로 합니다.

## Table of Contents

- [Features](#features)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Features

- 프로젝트 저장소 클론부터 POT/PO 준비, Weblate 프로젝트·컴포넌트 생성,
  번역 업로드까지 이어지는 5단계 마이그레이션 파이프라인 자동화
  (`weblate-migration/`)
- 단일 프로젝트 또는 프로젝트 × 버전 조합의 배치(batch) 마이그레이션 지원
- 마이그레이션 후 Zanata 원본과 Weblate 결과를 비교하는 정확도 테스트
- 프로젝트/버전/컴포넌트/로케일 단위 로그 및 요약 리포트(`report.md`) 생성
- Weblate 언어(로케일) 설정을 Zanata 정의와 동기화하는 보조 스크립트
  (`language/`)

## Repository Structure

| 경로 | 역할 |
|---|---|
| [`weblate-migration/`](weblate-migration/) | **핵심 마이그레이션 도구.** 프로젝트를 클론하고, POT/PO 파일을 준비하고, Weblate에 프로젝트/컴포넌트를 만들고, 번역을 업로드한 뒤 정확도를 검증합니다. |
| [`language/`](language/) | Weblate의 언어(로케일) 설정을 Zanata 쪽 정의와 맞추는 보조 스크립트. 언어 생성/수정/삭제를 Weblate REST API로 수행합니다. |
| [`docs/`](docs/) | 사용 가이드와 검증 리포트. |

## Prerequisites

- Python 3, pip, git
- `zanata-cli` 및 `~/.config/zanata.ini` 설정
- Weblate 접속 정보: `WEBLATE_URL`, `WEBLATE_TOKEN` 환경 변수
- `gettext`, `jq` 등 시스템 패키지 (`weblate-migration/01-setup-env/bindep.txt`
  참고, 스크립트가 자동 설치를 시도합니다)

자세한 확인 방법과 문제 해결은 [`docs/migration-guide.md`](docs/migration-guide.md)의
"2. 시작하기 전에 준비할 것", "7. 자주 겪는 문제" 절을 참고하세요.

## Quick Start

처음 사용한다면 **[`docs/migration-guide.md`](docs/migration-guide.md)**부터
읽어보세요. Zanata/Weblate, PO/POT 같은 용어를 모르는 사람도 따라올 수 있도록
준비물 → 실행 방법 → 5단계 내부 동작 → 로그/리포트 확인 → 자주 겪는 문제까지
순서대로 설명합니다.

프로젝트 하나만 마이그레이션하려면:

```bash
export WEBLATE_URL="https://your-weblate-instance.example.com"
export WEBLATE_TOKEN="발급받은 API 토큰"

cd weblate-migration
./migration_resources.sh <project_name> <version> <workspace_name>
# 예: ./migration_resources.sh horizon stable/2025.1 workspace
```

여러 프로젝트를 한 번에 처리하려면 `list.txt`(프로젝트 목록)와
`version.txt`(버전 목록)를 준비한 뒤 `./migration_projects.sh`를 실행하세요.
자세한 인자, 실행 중 표시되는 진행률, 로그 형식 등은
[`weblate-migration/README.md`](weblate-migration/README.md)와
[`docs/migration-guide.md`](docs/migration-guide.md)에 정리되어 있습니다.

## Documentation

| 문서 | 내용 |
|---|---|
| [`docs/migration-guide.md`](docs/migration-guide.md) | 초보자용 마이그레이션 사용 가이드 (한글) |
| [`weblate-migration/README.md`](weblate-migration/README.md) | 도구의 폴더 구조, 워크스페이스 레이아웃, 로그 형식 원문 (영문) |
| [`docs/horizon-test.md`](docs/horizon-test.md) | Horizon 프로젝트 실제 마이그레이션 검증 사례와 발견된 문제 유형 |
| [`docs/enhance-migration-accuracy.md`](docs/enhance-migration-accuracy.md) | 정확도 테스트(5단계)를 더 엄밀하게 만들기 위한 개선 방향 |
| [`docs/accury-test-issues.md`](docs/accury-test-issues.md) | 정확도 테스트를 수행하면서 겪은 주요 이슈들 |
| [`language/README.md`](language/README.md) | 언어(로케일) 설정 동기화 스크립트 사용법 (영문) |

## Contributing

버그 리포트, 기능 제안, PR 제출 절차는 [`CONTRIBUTING.md`](CONTRIBUTING.md)를
참고해주세요.

## License

[Apache License 2.0](LICENSE)

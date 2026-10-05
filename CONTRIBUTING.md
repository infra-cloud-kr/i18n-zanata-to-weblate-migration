# Contributing

이 저장소는 OpenStack I18n(국제화) SIG이 Zanata에서 Weblate로 번역 리소스를
옮기는 데 쓰는 도구입니다. 기여해주셔서 감사합니다. 아래 절차를 따라주시면
리뷰가 더 빨라집니다.

## 시작하기 전에

- 전체 구조와 사용법은 [`README.md`](README.md)를 먼저 읽어주세요.
- `weblate-migration/` 폴더에서 작업한다면 해당 폴더의
  [`CLAUDE.md`](weblate-migration/CLAUDE.md)에 그 폴더에만 적용되는 추가
  규칙이 있으니 함께 확인해주세요.

## 이슈 등록하기

버그·기능 제안·번역 정확도 문제는 모두
[GitHub Issues](https://github.com/openstack-kr/i18n-zanata-to-weblate-migration/issues)에
등록해주세요. 이슈 생성 시 아래 두 템플릿 중 상황에 맞는 것을 골라 작성하면 됩니다.

- **Bug report** — 스크립트 실행 자체가 실패하거나 예상과 다르게 동작하는 경우
- **Migration accuracy issue** — 스크립트는 성공했지만 Zanata 원본과 Weblate
  결과가 다른 경우 (예: 번역 미반영, fuzzy/plural 구조 손실)

## 개발 환경 설정

`weblate-migration/`의 스크립트를 직접 실행하며 검증하려면:

```bash
cd weblate-migration
python3 -m venv .venv
source .venv/bin/activate
pip install -r 01-setup-env/requirements.txt
```

시스템 패키지(`gettext`, `jq` 등)는 `01-setup-env/bindep.txt`에 정의되어
있습니다. `zanata-cli` 설치와 `WEBLATE_URL`/`WEBLATE_TOKEN` 환경 변수 설정
등 실행 전 준비물은 [`docs/migration-guide.md`](docs/migration-guide.md)의
"2. 시작하기 전에 준비할 것"을 참고해주세요.

## 브랜치 및 커밋 컨벤션

- PR은 `develop` 브랜치를 base로 보내주세요 (`main`이 아닙니다).
- 커밋 메시지는 이 저장소가 이미 쓰고 있는
  [Conventional Commits](https://www.conventionalcommits.org/) 스타일을
  따라주세요: `<type>: <한 줄 요약>` (예: `fix: WeblateRestService에 POST 메서드 추가`).
  - `feat`: 새로운 기능
  - `fix`: 버그 수정
  - `refactor`: 동작 변경 없는 구조 개편
  - `docs`: 문서만 변경
- 여러 하위 단계로 나뉜 작업이면 스코프를 붙여도 됩니다: `<type>(scope): <요약>`.

## 코드 스타일

- **Python**: `weblate-migration/tox.ini`의 `pep8` 환경(`flake8`)을 통과해야
  합니다. `tox -e pep8`로 확인하거나, venv에서 직접 `flake8`을 실행하세요.
- **Shell**: 새로 추가하거나 수정한 `.sh` 파일은 `bash -n <file>`로 문법
  오류가 없는지 확인해주세요.
- 기존 코드 스타일(네이밍, 로그 태깅 형식 등)을 최대한 따라주세요.

## 테스트 방법

이 저장소에는 자동화된 테스트 스위트가 없어서, PR을 보내기 전 아래를 직접
실행해 확인해주세요 (해당하는 항목만 실행하면 됩니다).

- [ ] 수정한 `.sh` 파일에 `bash -n` 실행
- [ ] 파일/폴더를 옮기거나 이름을 바꿨다면, 옛 경로에 대한 참조가 남아있지
      않은지 `grep -rn "<옛 경로>"`로 확인
- [ ] 가능하다면 실제 프로젝트 하나로 파이프라인(`migration_resources.sh`)을
      처음부터 끝까지 실행해 이전과 동일하게 동작하는지 확인
- [ ] Python을 변경했다면 `flake8`과 `python -m py_compile <file>` 통과 확인

## PR 제출 절차

1. 이슈가 있다면 먼저 연결해주세요 (`Closes #123`).
2. PR 템플릿의 각 섹션(요약, 변경 종류, 테스트 체크리스트, 문서 업데이트
   여부)을 채워주세요.
3. 리뷰 코멘트에 대한 수정은 새 커밋으로 추가해주세요 (히스토리를 보존하기
   위해 강제 push/rebase는 리뷰어 요청이 있을 때만 해주세요).
4. 머지는 관리자가 승인 후 진행합니다.

## 질문이 있다면

궁금한 점은 이슈를 열어 질문해주세요.

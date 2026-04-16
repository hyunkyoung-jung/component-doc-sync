# kpds-figma-sync-to-doc

Figma 컴포넌트 목록을 읽어 Confluence 페이지의 대상 표에 신규 항목만 추가하는 자동화 프로젝트입니다.

## 구성

- `figma_sync.py`: Figma/Confluence 동기화 메인 스크립트
- `.github/workflows/figma-sync.yml`: GitHub Actions 자동 실행 워크플로
- `.env.example`: 필요한 환경변수 예시
- `requirements.txt`: Python 의존성

## 로컬 실행

1. Python 3.11 이상을 준비합니다.
2. 가상환경을 만든 뒤 의존성을 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. 환경변수를 설정한 뒤 실행합니다.

```bash
export FIGMA_TOKEN=...
export FIGMA_FILE_KEY=...
export CONFLUENCE_DOMAIN=...
export CONFLUENCE_EMAIL=...
export CONFLUENCE_API_TOKEN=...
export CONFLUENCE_PAGE_ID=...
python figma_sync.py
```

## GitHub Actions 설정

GitHub 저장소의 `Settings > Secrets and variables > Actions` 에 아래 시크릿을 추가하세요.

- `FIGMA_TOKEN`
- `FIGMA_FILE_KEY`
- `CONFLUENCE_DOMAIN`
- `CONFLUENCE_EMAIL`
- `CONFLUENCE_API_TOKEN`
- `CONFLUENCE_PAGE_ID`

워크플로는 수동 실행만 지원합니다.

- 수동 실행: `workflow_dispatch`

## 참고

- 현재 워크플로는 저장소에 코드를 푸시하면 바로 사용할 수 있습니다.
- 정기 실행이 필요해지면 `.github/workflows/figma-sync.yml` 에 `schedule` 설정을 다시 추가하면 됩니다.

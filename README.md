# 💊 대전광역시 통합 약국 데이터 대시보드

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![Plotly Dash](https://img.shields.io/badge/Dash-4.1.0-008DE5?style=flat-square&logo=plotly&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=flat-square&logo=docker&logoColor=white)

대전광역시 5개 구(서구, 동구, 대덕구, 유성구, 중구)에서 제공하는 이기종 CSV 데이터셋을 실시간으로 파싱 및 통합하여, 인터랙티브하게 탐색할 수 있는 **프리미엄 웹 대시보드**입니다.

---

## 🌟 주요 특장점 (Key Features)

### 1. 이기종 데이터 파이프라인 자동 정규화
각 구청마다 배포하는 CSV 파일의 열 구조(약국명, 주소, 전화번호의 인덱스 위치)가 서로 다름을 파이썬 `pandas` 및 내장 CSV 모듈을 통해 완벽하게 정규화합니다.
* **서구**: 번호, 약국명칭, 약국주소, 전화번호
* **동구**: 번호, 약국명칭, 전화번호, 약국주소
* **유성구**: 구분코드, 기준, 약국명, 도로명주소, 전화번호 등

### 2. Jitter(분산 배치) 기반 지오코딩 최적화
수백 개의 주소를 실시간으로 외부 API에 지오코딩할 때 발생하는 **속도 저하 및 서버 차단(429 Rate Limit)**을 원천 차단하기 위해, 각 구별 중심가 좌표를 바탕으로 무작위 위경도 오프셋을 부여하는 **랜덤 분산 알고리즘(Jitter)**을 도입했습니다. 
* 이를 통해 대기 시간 없이 페이지 접속 즉시 수백 개의 마커가 겹침 없이 지도 위에 아름답게 시각화됩니다.

### 3. 글래스모피즘(Glassmorphism) 다크 테마 UI/UX
* **반응형 필터링**: 실시간 검색바 및 구별 라디오 버튼 클릭 즉시 사이드바 리스트와 산점도 지도가 부드럽게 연동됩니다.
* **고급 인터랙션**: 좌측 리스트의 약국 카드를 **클릭**하면, Plotly Mapbox가 해당 약국의 좌표로 즉시 **줌인 및 포커싱**되어 직관적인 위치 탐색을 지원합니다.

---

## 🚀 시작하기 (Getting Started)

본 프로젝트는 즉시 개발을 시작할 수 있도록 3가지 환경을 지원합니다. 팀원 협업 시에는 **방법 1 (GitHub Codespaces)**을 가장 권장합니다.

### ☁️ 방법 1: GitHub Codespaces에서 개발하기 (팀원 협업용 - 최우선 권장)
본 프로젝트는 로컬 환경 구성 없이 웹 브라우저에서 즉시 개발이 가능한 **GitHub Codespaces**를 지원합니다.
현재 **각 개발 팀원 이름으로 개별 브랜치(Branch)가 생성**되어 있으므로, 반드시 본인 이름의 브랜치에서 작업을 진행해 주세요.

1. GitHub 저장소 페이지 좌측 상단의 **브랜치 선택 버튼**(기본값: `main`)을 클릭하여 **본인 이름의 브랜치**로 먼저 이동합니다.
2. 본인 브랜치 화면에서 `<> Code` 버튼을 클릭하고 **Codespaces** 탭에서 `Create codespace on <본인 브랜치명>`을 클릭합니다.
3. VS Code 웹 에디터 하단 터미널(Terminal)이 열리면, 파이썬 의존성을 설치하고 대시보드 서버를 실행합니다.
   ```bash
   pip install -r requirements.txt
   python app.py
   ```
4. 하단 패널의 **Ports(포트)** 탭을 클릭한 뒤, `8050` 포트의 **브라우저에서 열기(지구본 아이콘)**를 눌러 실행된 화면을 확인하며 개발합니다.
5. 작업이 완료되면 커밋 후 푸시(`git push origin 본인이름`)하고 PR을 생성합니다.

---

### 📦 방법 2: Docker 기반 로컬 개발 환경 구성하기
도커를 활용하면 의존성 충돌 없이 완전히 격리된 환경에서 개발을 진행할 수 있습니다. `docker-compose.yml` 파일에 로컬 볼륨 매핑(`.:/app`)이 설정되어 있어 코드를 수정하면 컨테이너 내부에도 즉시 반영됩니다.

```bash
# 1. 저장소 클론
git clone <repository-url>
cd 대전광역시_약국지도

# 2. 도커 컨테이너 빌드 및 백그라운드 실행
docker compose up -d

# 3. 브라우저 접속하여 대시보드 확인
👉 http://localhost:8050/
```

> **💡 도커 환경 개발 팁**: 
> 로컬에서 `app.py`를 수정한 후 변경사항을 웹에 반영하려면 터미널에서 `docker compose restart` 명령어를 실행해 컨테이너를 재시작해 주세요.
> 개발을 마치고 컨테이너 리소스를 완전히 정리할 때는 `docker compose down` 명령어를 사용합니다.

---

### 🐍 방법 3: 로컬 Python 환경에서 실행
Docker나 Codespaces를 사용하지 않고 직접 Python을 구동하는 환경입니다. Python 3.10 이상이 설치되어 있어야 합니다.

```bash
# 1. 의존성 라이브러리 설치
pip install -r requirements.txt

# 2. 대시보드 서버 실행
python app.py

# 3. 브라우저 접속
👉 http://127.0.0.1:8050/
```

---

## 📁 프로젝트 구조 (Project Structure)

```text
.
├── app.py                   # 메인 Dash 대시보드 애플리케이션 (UI & 백엔드 통합)
├── requirements.txt         # 파이썬 의존성 명세 (Dash, Plotly, Pandas)
├── Dockerfile               # 경량 파이썬 실행 컨테이너 명세
├── docker-compose.yml       # 간편 오케스트레이션 설정
├── 대전광역시 *.csv          # 5개 구별 원본 약국 데이터셋
└── README.md                # 기술 명세서
```

---

## 🛠️ 기술 스택 (Tech Stack)
* **Core Backend**: Python 3.11, Pandas 3.0
* **Frontend Dashboard**: Plotly Dash 4.1, Dash Core Components
* **Mapping Engine**: Plotly Express Scatter Mapbox (`carto-darkmatter` 오픈소스 타일)
* **DevOps**: Docker, Docker Compose

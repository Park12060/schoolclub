# Python 3.11 슬림 이미지를 기반으로 설정 (안정성 및 경량화)
FROM python:3.14-slim

# 환경 변수 설정 (파이썬 버퍼링 제거 및 기본 인코딩 지정)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8

# 작업 디렉토리 생성
WORKDIR /app

# 시스템 의존성 업데이트 및 필수 라이브러리 설치 후 캐시 정리
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성 파일 복사 및 설치
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 소스 코드 및 데이터 파일 복사
COPY . /app/

# 컨테이너 노출 포트 설정 (Dash 기본 포트)
EXPOSE 8050

# 애플리케이션 실행 명령 (모든 인터페이스에서 접속 가능하도록 0.0.0.0 바인딩)
CMD ["python", "app.py"]

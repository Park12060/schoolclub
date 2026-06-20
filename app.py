import os
import csv
import json
import random
import ssl
import threading
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import math
from datetime import datetime, timezone, timedelta

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output, State, ctx

# ===== 0. 한국 표준시 (KST = UTC+9) =====
KST = timezone(timedelta(hours=9))

# SSL 컨텍스트 (HTTP→HTTPS 리다이렉트 처리)
# Using unverified SSL context to prevent certificate validation issues with public API
_SSL_CTX = ssl._create_unverified_context()

def now_kst():
    return datetime.now(KST)

# ===== 1. 공공 API 설정 =====
# Encoding Key (포털 제공 그대로 URL에 삽입)
API_KEY_ENC = '83SKSqIwUH1hqP5n5Kgu%2BVsqiEEA5FTEccrnqmQKMX86q%2FdSTuba7JsaB5yrYPA3ah6WyQP7l2L22QY%2FAEmotQ%3D%3D'
API_BASE = 'http://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyListInfoInqire'
API_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pharmacy_api_cache.json')

DISTRICTS = ['서구', '동구', '대덕구', '유성구', '중구']

# ===== 2. CSV 및 Fallback 설정 =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_CONFIGS = [
    {"file": "대전광역시 서구_약국현황_20250820.csv",    "gu": "서구",  "cols": {"name": 1, "addr": 2, "phone": 3}},
    {"file": "대전광역시 동구 약국 현황_20250701.csv",   "gu": "동구",  "cols": {"name": 1, "addr": 3, "phone": 2}},
    {"file": "대전광역시 대덕구_약국정보_20250101.csv",  "gu": "대덕구","cols": {"name": 0, "addr": 1, "phone": 2}},
    {"file": "대전광역시 유성구_약국현황_20250731.csv",  "gu": "유성구","cols": {"name": 2, "addr": 3, "phone": 4}},
    {"file": "대전광역시 중구 약국 정보_20250905.csv",   "gu": "중구",  "cols": {"name": 1, "addr": 4, "phone": 2}},
]

FALLBACK_COORDS = {
    "서구": (36.3554, 127.3838),
    "동구": (36.3315, 127.4545),
    "대덕구": (36.3466, 127.4157),
    "유성구": (36.3622, 127.3563),
    "중구": (36.3256, 127.4209),
}

GU_COLORS = {
    "서구": "#f5576c",
    "동구": "#4facfe",
    "대덕구": "#43e97b",
    "유성구": "#fee140",
    "중구": "#e879f9",
}

# 공공심야약국 판별 기준: 평일 22시 이후까지 운영
NIGHT_CLOSE_THRESHOLD = 2200  # 22:00 이후 마감이면 심야약국으로 분류

# ===== 3. 거리 계산 및 주소 추론 (Haversine Formula) =====
def calculate_distance(lat1, lon1, lat2, lon2):
    """
    두 좌표 사이의 거리를 킬로미터 단위로 계산 (Haversine 공식)
    """
    R = 6371  # 지구 반지름 (km)
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def infer_coordinates_from_address(address_text, pharmacies_df):
    """
    입력된 주소 텍스트로부터 좌표 추론
    1. 구 이름과 일치 확인 (예: "서구", "동구")
    2. 약국 주소와 일치 확인
    3. 모두 실패 시 None 반환
    """
    if not address_text:
        return None
    
    text = address_text.lower().strip()
    
    # 1. 구 이름 확인
    for gu, coords in FALLBACK_COORDS.items():
        if gu.lower() in text:
            return {"lat": coords[0], "lon": coords[1], "source": "gu_name"}
    
    # 2. 약국 주소 검색 (입력된 텍스트 포함)
    for _, row in pharmacies_df.iterrows():
        if text in row["address"].lower():
            return {"lat": row["lat"], "lon": row["lon"], "source": "pharmacy_address", "name": row["name"]}
    
    return None

# ===== 4. API & CSV 데이터 처리 로직 =====
def fetch_pharmacies_for_district(district: str, max_rows: int = 500) -> list:
    """공공 API로 약국 목록 + 운영시간 + 실제 좌표 조회 (전체 페이지 수집)"""
    city_enc = urllib.parse.quote('대전광역시')
    dist_enc = urllib.parse.quote(district)
    all_records = []
    page = 1

    while True:
        url = (f'{API_BASE}?serviceKey={API_KEY_ENC}'
               f'&Q0={city_enc}&Q1={dist_enc}'
               f'&pageNo={page}&numOfRows={max_rows}')
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/xml'
            })
            with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
                data = resp.read().decode('utf-8')
            root = ET.fromstring(data)
            result_code = root.findtext('.//resultCode', '99')
            if result_code != '00':
                print(f'[API] {district} resultCode={result_code}')
                break

            items = root.findall('.//item')
            if not items:
                break

            for item in items:
                def g(tag, _item=item):
                    return (_item.findtext(tag) or '').strip()

                lat_str = g('wgs84Lat')
                lon_str = g('wgs84Lon')
                try:
                    lat = float(lat_str)
                    lon = float(lon_str)
                    if not (35.0 < lat < 38.5 and 125.0 < lon < 130.0):
                        lat, lon = None, None
                except (ValueError, TypeError):
                    lat, lon = None, None

                all_records.append({
                    'hpid':    g('hpid'),
                    'name':    g('dutyName'),
                    'address': g('dutyAddr'),
                    'phone':   g('dutyTel1') or '정보 없음',
                    'district': district,
                    'lat':     lat,
                    'lon':     lon,
                    'time1s': g('dutyTime1s'), 'time1c': g('dutyTime1c'),
                    'time2s': g('dutyTime2s'), 'time2c': g('dutyTime2c'),
                    'time3s': g('dutyTime3s'), 'time3c': g('dutyTime3c'),
                    'time4s': g('dutyTime4s'), 'time4c': g('dutyTime4c'),
                    'time5s': g('dutyTime5s'), 'time5c': g('dutyTime5c'),
                    'time6s': g('dutyTime6s'), 'time6c': g('dutyTime6c'),
                    'time7s': g('dutyTime7s'), 'time7c': g('dutyTime7c'),
                    'time8s': g('dutyTime8s'), 'time8c': g('dutyTime8c'),
                })

            total = int(root.findtext('.//totalCount', '0') or 0)
            if page * max_rows >= total:
                break
            page += 1

        except Exception as e:
            print(f'[API] {district} p{page} 조회 실패: {e}')
            break

    return all_records


def load_api_cache() -> list:
    """캐시 파일이 있으면 로드"""
    if os.path.exists(API_CACHE_FILE):
        try:
            with open(API_CACHE_FILE, encoding='utf-8') as f:
                cached = json.load(f)
            print(f'[CACHE] {len(cached)}개 약국 데이터 로드 완료')
            return cached
        except Exception as e:
            print(f'[CACHE] 로드 실패: {e}')
    return []


def save_api_cache(records: list):
    try:
        with open(API_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f'[CACHE] {len(records)}개 저장 완료')
    except Exception as e:
        print(f'[CACHE] 저장 실패: {e}')


def fetch_all_from_api() -> list:
    """모든 구 약국 정보를 API에서 수집"""
    all_records = []
    for district in DISTRICTS:
        print(f'[API] {district} 약국 조회 중...')
        recs = fetch_pharmacies_for_district(district)
        print(f'[API] {district}: {len(recs)}개 수집')
        all_records.extend(recs)
    return all_records


def _parse_time(t: str) -> int:
    """'0900' → 900, '2130' → 2130, 빈 문자열 → -1"""
    try:
        return int(t) if t else -1
    except (ValueError, TypeError):
        return -1


def _time_in_range(start: int, end: int, current: int) -> bool:
    """시작~종료 범위 내에 현재 시간이 있는지 (자정 걸침 처리)"""
    if start < 0 or end < 0:
        return False
    if end < start:  # 자정 넘어가는 경우 (예: 2230~0100)
        return current >= start or current <= end
    return start <= current <= end


def is_open_now(row: dict, dt: datetime = None) -> bool:
    """현재 시각(KST) 기준으로 운영 중인지 판단"""
    if dt is None:
        dt = now_kst()
    
    weekday = dt.isoweekday()  # 1=월, 2=화, ..., 7=일
    current_time = dt.hour * 100 + dt.minute
    
    # 요일에 해당하는 시작/종료 가져오기
    prefix = f'time{weekday}'
    start = _parse_time(row.get(f'{prefix}s', ''))
    end   = _parse_time(row.get(f'{prefix}c', ''))
    
    return _time_in_range(start, end, current_time)


def is_night_pharmacy(row: dict) -> bool:
    """공공심야약국 판별: 평일 중 하나라도 22시 이후까지 운영"""
    # 월~일 중 최소 하나의 요일 마감이 NIGHT_CLOSE_THRESHOLD 이상이면 심야약국
    for i in range(1, 8):
        end = _parse_time(row.get(f'time{i}c', ''))
        if end >= NIGHT_CLOSE_THRESHOLD:
            return True
    # 공휴일 포함
    end8 = _parse_time(row.get('time8c', ''))
    if end8 >= NIGHT_CLOSE_THRESHOLD:
        return True
    return False


def get_operating_summary(row: dict) -> str:
    """약국 운영시간 요약 문자열 생성"""
    day_labels = ['월', '화', '수', '목', '금', '토', '일', '공휴일']
    parts = []
    for i, label in enumerate(day_labels, 1):
        s = _parse_time(row.get(f'time{i}s', ''))
        c = _parse_time(row.get(f'time{i}c', ''))
        if s >= 0 and c >= 0:
            s_str = f'{s:04d}'[:2] + ':' + f'{s:04d}'[2:]
            c_str = f'{c:04d}'[:2] + ':' + f'{c:04d}'[2:]
            parts.append(f'{label} {s_str}~{c_str}')
    return ' | '.join(parts) if parts else '운영시간 정보 없음'


def load_from_csv_fallback() -> list:
    """CSV에서 기본 데이터 로드 (운영시간 없음, 좌표 Jitter)"""
    records = []
    for cfg in CSV_CONFIGS:
        file_path = os.path.join(BASE_DIR, cfg["file"])
        if not os.path.exists(file_path):
            continue
        base_lat, base_lng = FALLBACK_COORDS[cfg["gu"]]
        try:
            with open(file_path, encoding="euc-kr", errors="ignore") as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    cols = cfg["cols"]
                    if len(row) <= max(cols.values()):
                        continue
                    name  = row[cols["name"]].strip().strip('"').strip("'")
                    addr  = row[cols["addr"]].strip().strip('"').strip("'")
                    phone = row[cols["phone"]].strip().strip('"').strip("'")
                    if len(addr) > 5:
                        records.append({
                            'hpid':     '',
                            'name':     name,
                            'address':  addr,
                            'phone':    phone or '정보 없음',
                            'district': cfg["gu"],
                            'lat':      base_lat + (random.random() - 0.5) * 0.05,
                            'lon':      base_lng + (random.random() - 0.5) * 0.05,
                            # 운영시간 없음
                            **{f'time{i}{s}': '' for i in range(1, 9) for s in ['s', 'c']}
                        })
        except Exception as e:
            print(f"[CSV] {cfg['file']} 로드 오류: {e}")
    return records


# ===== 5. 데이터 초기화 =====
def load_data() -> pd.DataFrame:
    # 1) API 캐시 먼저 시도
    api_data = load_api_cache()
    
    # 2) 캐시 없으면 API 호출 시도
    if not api_data:
        print('[INIT] API 캐시 없음 → API 직접 호출 시도...')
        api_data = fetch_all_from_api()
        if api_data:
            save_api_cache(api_data)
    
    # 3) API 실패 → CSV 폴백
    if not api_data:
        print('[INIT] API 실패 → CSV 폴백 모드')
        api_data = load_from_csv_fallback()
    else:
        print(f'[INIT] API 데이터 {len(api_data)}개 사용')
    
    df = pd.DataFrame(api_data)
    df['id'] = range(len(df))
    df['color'] = df['district'].map(GU_COLORS)
    
    # 좌표 없는 항목 Jitter 처리
    for idx, row in df.iterrows():
        if pd.isna(row.get('lat')) or row.get('lat') is None:
            base_lat, base_lng = FALLBACK_COORDS.get(row['district'], (36.35, 127.39))
            df.at[idx, 'lat'] = base_lat + (random.random() - 0.5) * 0.05
            df.at[idx, 'lon'] = base_lng + (random.random() - 0.5) * 0.05
    
    # 심야약국 여부 컬럼
    df['is_night'] = df.apply(lambda r: is_night_pharmacy(r.to_dict()), axis=1)
    
    return df


# 앱 시작 시 데이터 로드
df_pharmacies = load_data()
print(f'[READY] 총 {len(df_pharmacies)}개 약국 로드 / 심야약국 {df_pharmacies["is_night"].sum()}개')


# ===== 6. Dash 앱 초기화 =====
app = Dash(__name__, title="대전광역시 약국 대시보드")
server = app.server

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8">
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap" rel="stylesheet">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Noto Sans KR', sans-serif;
                background-color: #0b0f19;
                color: #e2e8f0;
                height: 100vh;
                overflow: hidden;
            }
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: transparent; }
            ::-webkit-scrollbar-thumb { background: rgba(99,179,237,0.3); border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: rgba(99,179,237,0.5); }

            /* 필터 버튼 */
            .filter-btn {
                padding: 6px 14px; border-radius: 20px; font-size: 13px;
                border: 1px solid rgba(255,255,255,0.15);
                background: rgba(255,255,255,0.05);
                color: #e2e8f0; cursor: pointer; transition: all 0.2s;
                font-family: 'Noto Sans KR', sans-serif;
            }
            .filter-btn:hover { background: rgba(99,179,237,0.15); border-color: rgba(99,179,237,0.4); }

            /* 운영 상태 뱃지 */
            .badge-open   { color: #48bb78; font-size: 11px; font-weight: 700; }
            .badge-closed { color: #fc8181; font-size: 11px; font-weight: 700; }
            .badge-night  { color: #b794f4; font-size: 11px; font-weight: 700; }

            /* 약국 카드 호버 */
            .pharm-card:hover {
                background: rgba(99,179,237,0.08) !important;
                border-color: rgba(99,179,237,0.3) !important;
                transform: translateX(2px);
            }

            /* 현재 시각 표시 */
            #clock-display {
                font-size: 12px; color: #718096; font-variant-numeric: tabular-nums;
            }

            /* 심야 강조 카드 */
            .night-card {
                border-color: rgba(183,148,244,0.35) !important;
                background: rgba(159,122,234,0.06) !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
        <script>
            // 전역 변수로 현재 사용자 위치 저장
            window.currentUserLocation = null;
            
            // Geolocation 및 거리 계산
            function getDistance(lat1, lon1, lat2, lon2) {
                const R = 6371; // 지구 반지름 (km)
                const dLat = (lat2 - lat1) * Math.PI / 180;
                const dLon = (lon2 - lon1) * Math.PI / 180;
                const a = 
                    Math.sin(dLat/2) * Math.sin(dLat/2) +
                    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                    Math.sin(dLon/2) * Math.sin(dLon/2);
                const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
                return (R * c).toFixed(2);
            }
            
            // GPS 위치 요청 함수
            function getLocation() {
                if (!navigator.geolocation) {
                    alert("브라우저가 Geolocation을 지원하지 않습니다.");
                    return;
                }
                
                // 로딩 상태 표시
                const btn = document.getElementById('gps-button');
                if (btn) {
                    btn.textContent = '⏳ 위치 검색 중...';
                    btn.disabled = true;
                }
                
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        const coords = {
                            lat: position.coords.latitude,
                            lng: position.coords.longitude,
                            accuracy: position.coords.accuracy
                        };
                        window.currentUserLocation = coords;
                        
                        // Dash 콜백 트리거를 위해 Store 업데이트
                        const event = new CustomEvent('userLocationUpdate', { detail: coords });
                        document.dispatchEvent(event);
                        
                        // 버튼 상태 복원
                        if (btn) {
                            btn.textContent = '📍 위치 추적 허용';
                            btn.disabled = false;
                            btn.style.backgroundColor = 'rgba(99, 179, 237, 0.3)';
                            btn.style.borderColor = 'rgba(99, 179, 237, 0.8)';
                        }
                        
                        console.log('위치 정보 획득:', coords);
                    },
                    function(error) {
                        console.error("위치 정보 오류:", error.message);
                        alert("위치 접근이 거부되었습니다.\\n브라우저 설정을 확인하세요.");
                        
                        // 버튼 상태 복원
                        if (btn) {
                            btn.textContent = '📍 위치 추적 허용';
                            btn.disabled = false;
                        }
                    },
                    { 
                        enableHighAccuracy: true, 
                        timeout: 10000, 
                        maximumAge: 0 
                    }
                );
            }
        </script>
    </body>
</html>
'''

# ===== 7. 레이아웃 =====
app.layout = html.Div([

    # ── 상단 헤더 ──
    html.Header([
        # 제목 + 시각
        html.Div([
            html.H1("💊 대전광역시 약국 대시보드", style={
                "fontSize": "20px", "fontWeight": "700",
                "background": "linear-gradient(135deg, #63b3ed, #9f7aea)",
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent"
            }),
            html.Div(id="clock-display"),
        ], style={"display": "flex", "flexDirection": "column", "gap": "2px"}),

        # 현재 위치 입력
        html.Div(
            [dcc.Input(
                id="location-input", type="text", placeholder="📍 현재 위치 (예: 서구, 중구, 약국명...)",
                style={
                    "width": "220px", "padding": "8px 16px", "borderRadius": "20px",
                    "border": "1px solid rgba(99,179,237,0.3)", "backgroundColor": "rgba(255,255,255,0.05)",
                    "color": "#fff", "outline": "none", "fontSize": "13px"
                }
            )],
            style={"maxWidth": "230px", "margin": "0 8px"},
            title="구(서구, 동구 등) 또는 약국명을 입력하면 그 근처 약국 5개가 자동 표시됩니다."
        ),
        
        # 위치 추적 허용 버튼
        html.Button(
            "📍 위치 추적 허용",
            id="gps-button",
            n_clicks=0,
            style={
                "padding": "8px 14px", "borderRadius": "20px", "fontSize": "13px",
                "border": "1px solid rgba(99,179,237,0.5)", "backgroundColor": "rgba(99,179,237,0.15)",
                "color": "#63b3ed", "cursor": "pointer", "transition": "all 0.2s",
                "fontWeight": "500"
            }
        ),

        # 검색바
        html.Div([
            dcc.Input(
                id="search-input", type="text",
                placeholder="약국명 또는 주소 검색...",
                debounce=True,
                style={
                    "width": "220px", "padding": "8px 16px", "borderRadius": "20px",
                    "border": "1px solid rgba(99,179,237,0.3)",
                    "backgroundColor": "rgba(255,255,255,0.05)",
                    "color": "#fff", "outline": "none", "fontSize": "13px"
                }
            )
        ], style={"flex": "1", "maxWidth": "230px", "margin": "0 8px"}),

        # 구별 필터
        dcc.RadioItems(
            id="district-filter",
            options=[
                {"label": "전체",  "value": "전체"},
                {"label": "서구",  "value": "서구"},
                {"label": "동구",  "value": "동구"},
                {"label": "대덕구","value": "대덕구"},
                {"label": "유성구","value": "유성구"},
                {"label": "중구",  "value": "중구"},
            ],
            value="전체", inline=True,
            style={"display": "flex", "gap": "8px"},
            inputStyle={"display": "none"},
            labelStyle={
                "padding": "6px 12px", "borderRadius": "20px", "fontSize": "12px",
                "border": "1px solid rgba(255,255,255,0.15)",
                "backgroundColor": "rgba(255,255,255,0.05)",
                "cursor": "pointer", "transition": "all 0.2s", "color": "#e2e8f0"
            }
        ),

        # ── 운영 상태 / 심야 필터 ──
        html.Div([
            dcc.RadioItems(
                id="pharmacy-type-filter",
                options=[
                    {"label": "🏪 전체",      "value": "all"},
                    {"label": "🟢 운영 중",   "value": "open"},
                    {"label": "🌙 공공심야약국", "value": "night"},
                ],
                value="all", inline=True,
                style={"display": "flex", "gap": "8px"},
                inputStyle={"display": "none"},
                labelStyle={
                    "padding": "6px 12px", "borderRadius": "20px", "fontSize": "12px",
                    "border": "1px solid rgba(255,255,255,0.15)",
                    "backgroundColor": "rgba(255,255,255,0.05)",
                    "cursor": "pointer", "transition": "all 0.2s", "color": "#e2e8f0"
                }
            )
        ], style={"marginLeft": "8px"}),

        # 카운터
        html.Div([
            html.Div(id="stat-counter", style={"fontSize": "18px", "fontWeight": "700", "color": "#63b3ed"}),
            html.Div("검색된 약국", style={"fontSize": "10px", "color": "#718096"})
        ], style={"textAlign": "center", "marginLeft": "12px", "minWidth": "60px"}),

    ], style={
        "display": "flex", "alignItems": "center", "justifyContent": "space-between",
        "padding": "10px 20px",
        "backgroundColor": "#121723",
        "borderBottom": "1px solid rgba(99,179,237,0.15)",
        "boxShadow": "0 4px 20px rgba(0,0,0,0.3)",
        "height": "68px", "flexWrap": "nowrap", "gap": "4px"
    }),

    # ── 데이터 소스 표시줄 ──
    html.Div(id="data-source-banner", style={
        "padding": "5px 20px", "fontSize": "11px",
        "backgroundColor": "#0e1420",
        "borderBottom": "1px solid rgba(255,255,255,0.06)",
        "color": "#4a5568", "display": "flex", "alignItems": "center", "gap": "12px"
    }),

    # ── 메인 (좌측 카드 + 우측 지도) ──
    html.Div([
        # 좌측 스크롤 리스트
        html.Div([
            html.Div(id="pharmacy-cards-container", style={
                "display": "flex", "flexDirection": "column", "gap": "8px",
                "padding": "12px", "overflowY": "auto", "height": "100%"
            })
        ], style={
            "width": "340px", "backgroundColor": "#161b29",
            "borderRight": "1px solid rgba(99,179,237,0.12)",
            "height": "calc(100vh - 96px)", "flexShrink": "0"
        }),

        # 우측 지도
        html.Div([
            dcc.Graph(
                id="pharmacy-map",
                style={"height": "100%", "width": "100%"},
                config={"displayModeBar": False}
            )
        ], style={"flex": "1", "height": "calc(100vh - 96px)"}),

    ], style={"display": "flex", "height": "calc(100vh - 96px)"}),

    # ── 스토어 & 인터벌 ──
    dcc.Store(id="selected-card-store", data=None),
    dcc.Store(id="user-location-store", data=None),
    dcc.Store(id="nearby-pharmacies-store", data=None),
    # 1분마다 현재시간 갱신 (운영 상태 자동 업데이트)
    dcc.Interval(id="clock-interval", interval=60_000, n_intervals=0),
])


# ===== 8. 콜백 (상호작용 처리) =====

# (A) 시계 업데이트
@app.callback(
    Output("clock-display", "children"),
    Input("clock-interval", "n_intervals")
)
def update_clock(_):
    dt = now_kst()
    weekday_map = ['월', '화', '수', '목', '금', '토', '일']
    wd = weekday_map[dt.weekday()]
    return f"⏰ {dt.strftime('%Y.%m.%d')} ({wd}) {dt.strftime('%H:%M')} KST"


# (B) 데이터 소스 배너
@app.callback(
    Output("data-source-banner", "children"),
    Input("clock-interval", "n_intervals")
)
def update_banner(_):
    has_api = os.path.exists(API_CACHE_FILE)
    night_count = int(df_pharmacies['is_night'].sum())
    
    if has_api:
        src = html.Span([
            html.Span("✅ ", style={"color": "#48bb78"}),
            "공공 API 데이터 (국립중앙의료원 전국 약국 정보 조회 서비스) · 운영시간 실시간 반영"
        ])
    else:
        src = html.Span([
            html.Span("⚠️ ", style={"color": "#ed8936"}),
            "CSV 데이터 모드 (운영시간 정보 없음) · API 연결 시 자동 전환"
        ])
    return [
        src,
        html.Span(f"🌙 공공심야약국 {night_count}개 포함", style={"color": "#b794f4", "fontWeight": "600"}),
        html.Span(f"총 {len(df_pharmacies):,}개 약국", style={"color": "#63b3ed"}),
    ]


# (C) 카드 목록 + 카운터
@app.callback(
    Output("pharmacy-cards-container", "children"),
    Output("stat-counter", "children"),
    Input("search-input", "value"),
    Input("district-filter", "value"),
    Input("pharmacy-type-filter", "value"),
    Input("nearby-pharmacies-store", "data"),
    Input("clock-interval", "n_intervals"),
)
def update_sidebar(search_val, district_val, type_filter, nearby_data, _intervals):
    dt = now_kst()
    dff = df_pharmacies.copy()

    # 근처 약국 필터링 (GPS/위치입력 기반)
    show_nearby = False
    nearby_info_dict = {}
    if nearby_data:
        nearby_ids = nearby_data.get("pharmacy_ids", [])
        nearby_info = nearby_data.get("info", [])
        if nearby_ids and nearby_info:
            show_nearby = True
            # 거리순으로 정렬된 약국들로 필터링
            dff = dff[dff["id"].isin(nearby_ids)]
            # nearby_info의 순서대로 정렬
            dff = dff.set_index("id").loc[[p["id"] for p in nearby_info]].reset_index()
            nearby_info_dict = {p["id"]: p for p in nearby_info}

    # 구 필터
    if district_val and district_val != "전체" and not show_nearby:
        dff = dff[dff["district"] == district_val]

    # 검색 필터
    if search_val and not show_nearby:
        q = search_val.lower().strip()
        dff = dff[
            dff["name"].str.lower().str.contains(q, na=False) |
            dff["address"].str.lower().str.contains(q, na=False)
        ]

    # 운영 상태 / 심야 필터
    if type_filter == "open" and not show_nearby:
        dff = dff[dff.apply(lambda r: is_open_now(r.to_dict(), dt), axis=1)]
    elif type_filter == "night" and not show_nearby:
        dff = dff[dff["is_night"] == True]

    # 통계 문자열
    count_str = f"{len(dff):,}개"
    if show_nearby:
        count_str = f"⭐ 근처 {len(dff)}개"

    cards = []
    for _, row in dff.iterrows():
        row_dict = row.to_dict()
        open_now = is_open_now(row_dict, dt)
        night    = row["is_night"]
        color    = row["color"]

        # 운영 상태 뱃지
        if open_now:
            status_badge = html.Span("🟢 운영 중", className="badge-open")
        else:
            status_badge = html.Span("🔴 영업 종료", className="badge-closed")

        # 심야약국 특수 뱃지
        night_badge = html.Span(" 🌙 심야약국", className="badge-night") if night else None

        # 운영시간 요약
        ops = get_operating_summary(row_dict)
        ops_short = ops[:60] + '...' if len(ops) > 60 else ops

        # 근처 약국 정보 추가
        distance_text = ""
        rank_text = ""
        if show_nearby and row["id"] in nearby_info_dict:
            info = nearby_info_dict[row["id"]]
            distance_text = f" • {info['distance']:.2f}km"
            rank_text = f"#{info['rank']} "
            badge_color = "#ff6b6b"  # 강조 색상
        else:
            badge_color = color

        card_style = {
            "padding": "12px 14px", "borderRadius": "12px",
            "backgroundColor": "rgba(255,255,255,0.03)",
            "border": "1px solid rgba(255,255,255,0.08)",
            "cursor": "pointer", "transition": "all 0.2s",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.2)"
        }
        if night:
            card_style["borderColor"] = "rgba(183,148,244,0.35)"
            card_style["backgroundColor"] = "rgba(159,122,234,0.06)"
        if show_nearby:
            card_style["borderColor"] = "rgba(255,107,107,0.35)"

        card = html.Div([
            # 상단 행: 구 뱃지 + 상태뱃지
            html.Div([
                html.Span(f"{rank_text}{row['district']}", style={
                    "backgroundColor": f"{badge_color}22", "color": badge_color,
                    "padding": "2px 8px", "borderRadius": "10px",
                    "fontSize": "11px", "fontWeight": "700"
                }),
                html.Div([status_badge, night_badge], style={"display": "flex", "gap": "4px", "alignItems": "center"})
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center", "marginBottom": "6px"}),

            # 약국명
            html.Div(row["name"], style={
                "fontSize": "14px", "fontWeight": "700",
                "color": "#fff", "marginBottom": "4px"
            }),
            # 주소
            html.Div(f"📍 {row['address']}{distance_text}", style={
                "fontSize": "11px", "color": "#a0aec0",
                "marginBottom": "3px", "lineHeight": "1.4"
            }),
            # 전화
            html.Div(f"📞 {row['phone']}", style={
                "fontSize": "11px", "color": "#9f7aea", "fontWeight": "500",
                "marginBottom": "3px"
            }),
            # 운영시간 (API 데이터인 경우만)
            html.Div(f"🕐 {ops_short}", style={
                "fontSize": "10px", "color": "#4a5568",
                "display": "none" if ops == '운영시간 정보 없음' else "block"
            }),
        ],
        id={"type": "pharm-card", "index": int(row["id"])},
        n_clicks=0,
        style=card_style,
        className="pharm-card"
        )
        cards.append(card)

    if not cards:
        msg = {
            "open": "🟢 현재 운영 중인 약국이 없습니다.",
            "night": "🌙 공공심야약국이 없습니다.",
            "all": "조건에 맞는 약국이 없습니다."
        }.get(type_filter, "조건에 맞는 약국이 없습니다.")
        if show_nearby:
            msg = "📍 주변에 검색된 약국이 없습니다."
        cards.append(html.Div(msg, style={
            "color": "#718096", "textAlign": "center",
            "marginTop": "40px", "fontSize": "13px", "lineHeight": "1.8"
        }))

    return cards, count_str


# (D) 지도 업데이트
@app.callback(
    Output("pharmacy-map", "figure"),
    Input("search-input", "value"),
    Input("district-filter", "value"),
    Input("pharmacy-type-filter", "value"),
    Input("selected-card-store", "data"),
    Input("nearby-pharmacies-store", "data"),
    Input("clock-interval", "n_intervals"),
)
def update_map(search_val, district_val, type_filter, selected_data, nearby_data, _intervals):
    dt = now_kst()
    dff = df_pharmacies.copy()

    show_nearby = False
    user_coords = None
    if nearby_data:
        nearby_ids = nearby_data.get("pharmacy_ids", [])
        if nearby_ids:
            show_nearby = True
            dff = dff[dff["id"].isin(nearby_ids)]
            user_coords = nearby_data.get("user_location")

    if district_val and district_val != "전체" and not show_nearby:
        dff = dff[dff["district"] == district_val]
    if search_val and not show_nearby:
        q = search_val.lower().strip()
        dff = dff[
            dff["name"].str.lower().str.contains(q, na=False) |
            dff["address"].str.lower().str.contains(q, na=False)
        ]
    if type_filter == "open" and not show_nearby:
        dff = dff[dff.apply(lambda r: is_open_now(r.to_dict(), dt), axis=1)]
    elif type_filter == "night" and not show_nearby:
        dff = dff[dff["is_night"] == True]

    # 운영 상태 + 심야 분류
    dff = dff.copy()
    dff['open_now'] = dff.apply(lambda r: is_open_now(r.to_dict(), dt), axis=1)

    center_lat, center_lng = 36.3504, 127.3845
    zoom_level = 11.5

    # 우선순위 1: 선택된 카드로 포커싱
    if selected_data is not None:
        target_row = dff[dff["id"] == selected_data]
        if not target_row.empty:
            center_lat = target_row.iloc[0]["lat"]
            center_lng = target_row.iloc[0]["lon"]
            zoom_level = 15.5
    # 우선순위 2: 근처 약국(GPS/위치입력)으로 포커싱
    elif show_nearby and not dff.empty:
        center_lat = dff["lat"].mean()
        center_lng = dff["lon"].mean()
        zoom_level = 13.5
        if user_coords:
            center_lat = user_coords.get("lat", center_lat)
            center_lng = user_coords.get("lng", center_lng)

    fig = go.Figure()

    # ── 일반 약국 (운영 종료) ──
    df_normal_closed = dff[(~dff['is_night']) & (~dff['open_now'])]
    if not df_normal_closed.empty:
        fig.add_trace(go.Scattermapbox(
            lat=df_normal_closed['lat'], lon=df_normal_closed['lon'],
            mode='markers',
            marker=dict(size=8, color=df_normal_closed['color'].tolist(), opacity=0.45),
            text=df_normal_closed['name'],
            customdata=df_normal_closed[['address', 'phone', 'district']].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "📍 %{customdata[0]}<br>"
                "📞 %{customdata[1]}<br>"
                "🔴 영업 종료<extra></extra>"
            ),
            name='영업 종료'
        ))

    # ── 일반 약국 (운영 중) ──
    df_normal_open = dff[(~dff['is_night']) & (dff['open_now'])]
    if not df_normal_open.empty:
        fig.add_trace(go.Scattermapbox(
            lat=df_normal_open['lat'], lon=df_normal_open['lon'],
            mode='markers',
            marker=dict(size=12, color=df_normal_open['color'].tolist(), opacity=0.9),
            text=df_normal_open['name'],
            customdata=df_normal_open[['address', 'phone', 'district']].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "📍 %{customdata[0]}<br>"
                "📞 %{customdata[1]}<br>"
                "🟢 운영 중<extra></extra>"
            ),
            name='운영 중'
        ))

    # ── 심야약국 (영업 종료) ──
    df_night_closed = dff[(dff['is_night']) & (~dff['open_now'])]
    if not df_night_closed.empty:
        fig.add_trace(go.Scattermapbox(
            lat=df_night_closed['lat'], lon=df_night_closed['lon'],
            mode='markers',
            marker=dict(size=11, color='#9f7aea', opacity=0.6, symbol='circle'),
            text=df_night_closed['name'],
            customdata=df_night_closed[['address', 'phone', 'district']].values,
            hovertemplate=(
                "<b>🌙 %{text}</b><br>"
                "📍 %{customdata[0]}<br>"
                "📞 %{customdata[1]}<br>"
                "🌙 공공심야약국 (현재 종료)<extra></extra>"
            ),
            name='🌙 심야약국 (종료)'
        ))

    # ── 심야약국 (운영 중) ── 최강조
    df_night_open = dff[(dff['is_night']) & (dff['open_now'])]
    if not df_night_open.empty:
        fig.add_trace(go.Scattermapbox(
            lat=df_night_open['lat'], lon=df_night_open['lon'],
            mode='markers',
            marker=dict(size=16, color='#b794f4', opacity=1.0),
            text=df_night_open['name'],
            customdata=df_night_open[['address', 'phone', 'district']].values,
            hovertemplate=(
                "<b>🌙 %{text}</b><br>"
                "📍 %{customdata[0]}<br>"
                "📞 %{customdata[1]}<br>"
                "🟢 지금 운영 중인 심야약국!<extra></extra>"
            ),
            name='🌙 심야약국 (운영 중)'
        ))

    # ── 사용자 위치 표시 ──
    if user_coords:
        fig.add_trace(go.Scattermapbox(
            lat=[user_coords.get("lat")], lon=[user_coords.get("lng")],
            mode='markers',
            marker=dict(size=18, color='#3182ce', opacity=0.9, symbol='star'),
            text=['내 위치'],
            hovertemplate="<b>📍 내 위치</b><extra></extra>",
            name='📍 내 위치'
        ))

    fig.update_layout(
        mapbox_style="carto-darkmatter",
        mapbox=dict(center={"lat": center_lat, "lon": center_lng}, zoom=zoom_level),
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor="#0b0f19",
        plot_bgcolor="#0b0f19",
        legend=dict(
            orientation="h", yanchor="top", y=0.98, xanchor="left", x=0.02,
            bgcolor="rgba(18,23,35,0.85)", bordercolor="rgba(99,179,237,0.3)",
            borderwidth=1, font=dict(color="#fff", size=11), title=None
        ),
        uirevision="constant"  # 지도 뷰 유지
    )
    return fig


# (E) 카드 클릭 → 지도 이동
@app.callback(
    Output("selected-card-store", "data"),
    Input({"type": "pharm-card", "index": "ALL"}, "n_clicks"),
    State({"type": "pharm-card", "index": "ALL"}, "id"),
)
def handle_card_click(n_clicks_list, id_list):
    if not ctx.triggered:
        return None
    triggered_prop = ctx.triggered[0]["prop_id"]
    try:
        import json as _json
        clicked_id_dict = _json.loads(triggered_prop.split(".")[0])
        clicked_idx = clicked_id_dict["index"]
        for clicks, card_id in zip(n_clicks_list, id_list):
            if card_id["index"] == clicked_idx and clicks > 0:
                return clicked_idx
    except Exception:
        pass
    return None


# (F) 사용자 위치 기반 근처 약국 5개 계산
@app.callback(
    Output("nearby-pharmacies-store", "data"),
    Input("user-location-store", "data"),
    Input("location-input", "value"),
    prevent_initial_call=True
)
def calculate_nearby_pharmacies(location_data, location_text):
    """
    GPS 위치 또는 주소 입력을 기반으로 근처 약국 5개 계산
    우선순위: GPS(위치 추적) > 주소 입력
    """
    user_lat = None
    user_lng = None
    source = None
    
    # 1. GPS 데이터 우선 (위치 추적 허용 시)
    if location_data and location_data.get("lat") is not None:
        user_lat = location_data.get("lat")
        user_lng = location_data.get("lng")
        source = "gps"
    
    # 2. 주소 입력 처리 (위치 추적 미허용 시)
    elif location_text and len(location_text.strip()) >= 2:
        coords = infer_coordinates_from_address(location_text, df_pharmacies)
        if coords:
            user_lat = coords["lat"]
            user_lng = coords["lon"]  # Note: we use 'lon' in df_pharmacies
            source = "address_input"
    
    # 좌표가 없으면 None 반환
    if user_lat is None or user_lng is None:
        return None
    
    # 모든 약국과의 거리 계산
    distances = []
    for _, row in df_pharmacies.iterrows():
        dist = calculate_distance(user_lat, user_lng, row["lat"], row["lon"])
        distances.append({
            "id": row["id"],
            "name": row["name"],
            "address": row["address"],
            "phone": row["phone"],
            "distance": dist,
            "lat": row["lat"],
            "lon": row["lon"],
            "district": row["district"]
        })
    
    # 거리순으로 정렬하여 상위 5개 선택
    distances.sort(key=lambda x: x["distance"])
    nearby_5 = distances[:5]
    
    # 정보 추가 (순위, 거리 등)
    pharmacy_info = []
    for rank, pharm in enumerate(nearby_5, 1):
        pharmacy_info.append({
            "id": pharm["id"],
            "rank": rank,
            "distance": pharm["distance"],
            "name": pharm["name"]
        })
    
    return {
        "pharmacy_ids": [p["id"] for p in nearby_5],
        "info": pharmacy_info,
        "user_location": {"lat": user_lat, "lng": user_lng},
        "source": source
    }


# Clientside callback to get browser geolocation
app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks || n_clicks === 0) {
            return window.dash_clientside.no_update;
        }
        
        // Geolocation API 호출
        return new Promise(function(resolve) {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        resolve({
                            lat: position.coords.latitude,
                            lng: position.coords.longitude,
                            accuracy: position.coords.accuracy,
                            timestamp: new Date().toISOString()
                        });
                    },
                    function(error) {
                        console.error('위치 정보 오류:', error);
                        resolve({
                            lat: 36.3209,
                            lng: 127.4209,
                            error: error.message
                        });
                    },
                    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                );
            } else {
                resolve({ error: 'Geolocation not supported' });
            }
        });
    }
    """,
    Output("user-location-store", "data"),
    Input("gps-button", "n_clicks"),
    prevent_initial_call=True
)


# ===== 9. 백그라운드 API 갱신 (캐시 없을 때 비동기 수집) =====
def background_api_fetch():
    """앱 시작 후 백그라운드에서 API 데이터 수집 (캐시 없을 때만)"""
    if os.path.exists(API_CACHE_FILE):
        return  # 캐시 있으면 스킵
    print('[BG] 백그라운드 API 수집 시작...')
    records = fetch_all_from_api()
    if records:
        save_api_cache(records)
        print(f'[BG] API 수집 완료: {len(records)}개 → 재시작하면 API 데이터가 적용됩니다.')
    else:
        print('[BG] API 수집 실패 (키 미등록 또는 네트워크 오류)')


if __name__ == "__main__":
    import sys, io
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # 백그라운드 API 수집 스레드
    t = threading.Thread(target=background_api_fetch, daemon=True)
    t.start()

    is_docker = os.environ.get("DOCKER_ENV", False)
    debug_mode = not is_docker

    print("🚀 대전 약국 대시보드 서버 시작...")
    print("👉 로컬 접속: http://127.0.0.1:8050/")
    
    app.run(
        host="0.0.0.0",
        port=8050,
        debug=debug_mode,
        dev_tools_hot_reload=False,
        dev_tools_ui=False
    )

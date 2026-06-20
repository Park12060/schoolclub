import random
from pathlib import Path

import pandas as pd
import plotly.express as px

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "대전광역시 중구 약국 정보_20250905 (1).csv"
OUTPUT_FILE = BASE_DIR / "junggu_pharmacy_map.html"

if not CSV_FILE.exists():
    raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {CSV_FILE}")

# CSV 읽기
raw_df = pd.read_csv(CSV_FILE, encoding="utf-8-sig", dtype=str)
raw_df.columns = [col.strip() for col in raw_df.columns]

# 컬럼 이름 추출
name_col = next((c for c in raw_df.columns if "약국명" in c), None)
addr_col = next((c for c in raw_df.columns if "소재지" in c or "주소" in c), None)
phone_col = next((c for c in raw_df.columns if "전화" in c), None)

if not name_col or not addr_col or not phone_col:
    raise ValueError("CSV에서 필요한 열을 찾을 수 없습니다. 약국명칭, 소재지(도로명), 약국전화번호 열을 확인하세요.")

# 필요한 열 선택 및 정리
pharmacies = raw_df[[name_col, addr_col, phone_col]].rename(
    columns={name_col: "name", addr_col: "address", phone_col: "phone"}
).copy()
pharmacies["name"] = pharmacies["name"].astype(str).str.strip()
pharmacies["address"] = pharmacies["address"].astype(str).str.strip()
pharmacies["phone"] = pharmacies["phone"].astype(str).str.strip()
pharmacies = pharmacies[pharmacies["address"].str.len() > 5].reset_index(drop=True)

# 중구 중심 좌표와 Jitter 설정
CENTER_LAT, CENTER_LON = 36.3256, 127.4209
random.seed(42)
pharmacies["lat"] = pharmacies.index.to_series().apply(
    lambda _: CENTER_LAT + (random.random() - 0.5) * 0.04
)
pharmacies["lon"] = pharmacies.index.to_series().apply(
    lambda _: CENTER_LON + (random.random() - 0.5) * 0.04
)

# 지도 생성
fig = px.scatter_mapbox(
    pharmacies,
    lat="lat",
    lon="lon",
    hover_name="name",
    hover_data={"address": True, "phone": True},
    zoom=13,
    center={"lat": CENTER_LAT, "lon": CENTER_LON},
    height=800,
    width=1200,
    title="대전광역시 중구 약국 위치"
)
fig.update_traces(marker=dict(size=10, color="#FF6B6B", opacity=0.9))
fig.update_layout(
    mapbox_style="open-street-map",
    margin={"l": 0, "r": 0, "t": 60, "b": 0},
    paper_bgcolor="white",
    plot_bgcolor="white",
    title_font_size=24
)

# 결과 저장
fig.write_html(OUTPUT_FILE, include_plotlyjs="cdn")
print(f"대전광역시 중구 약국 위치 지도가 생성되었습니다: {OUTPUT_FILE}")

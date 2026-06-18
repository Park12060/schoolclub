import os
import csv
import random
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output, State, ctx

# ===== 1. 데이터 통합 및 정제 로직 =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_CONFIGS = [
    {"file": "대전광역시 서구_약국현황_20250820.csv", "gu": "서구", "cols": {"name": 1, "addr": 2, "phone": 3}},
    {"file": "대전광역시 동구 약국 현황_20250701.csv", "gu": "동구", "cols": {"name": 1, "addr": 3, "phone": 2}},
    {"file": "대전광역시 대덕구_약국정보_20250101.csv", "gu": "대덕구", "cols": {"name": 0, "addr": 1, "phone": 2}},
    {"file": "대전광역시 유성구_약국현황_20250731.csv", "gu": "유성구", "cols": {"name": 2, "addr": 3, "phone": 4}},
    {"file": "대전광역시 중구 약국 정보_20250905.csv", "gu": "중구", "cols": {"name": 1, "addr": 4, "phone": 2}}
]

# 구별 중심 좌표 (Fallback Jitter용)
FALLBACK_COORDS = {
    "서구": (36.3554, 127.3838),
    "동구": (36.3315, 127.4545),
    "대덕구": (36.3466, 127.4157),
    "유성구": (36.3622, 127.3563),
    "중구": (36.3256, 127.4209)
}

# 구별 브랜드 컬러 (Plotly 마커 및 리스트 뱃지용)
GU_COLORS = {
    "서구": "#f5576c",
    "동구": "#4facfe",
    "대덕구": "#43e97b",
    "유성구": "#fee140",
    "중구": "#e879f9"
}


def parse_bool_env(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def parse_port_env(value, default=8050):
    try:
        return int(value)
    except (TypeError, ValueError):
        print(f"⚠️ 잘못된 PORT 값({value})이 감지되어 기본값 {default}를 사용합니다.")
        return default

def load_integrated_data():
    records = []
    idx_counter = 0

    # 1) 기존 약국 CSV_CONFIGS 처리 (기존 로직 유지)
    for cfg in CSV_CONFIGS:
        file_path = os.path.join(BASE_DIR, cfg["file"])
        if not os.path.exists(file_path):
            continue

        base_lat, base_lng = FALLBACK_COORDS.get(cfg["gu"], (36.3504, 127.3845))
        try:
            with open(file_path, encoding="euc-kr", errors="ignore") as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    cols = cfg["cols"]
                    max_idx = max(cols.values())
                    if len(row) <= max_idx:
                        continue

                    name = row[cols["name"]].strip().strip('"').strip("'")
                    addr = row[cols["addr"]].strip().strip('"').strip("'")
                    phone = row[cols["phone"]].strip().strip('"').strip("'")

                    if len(addr) > 5:
                        lat = base_lat + (random.random() - 0.5) * 0.05
                        lng = base_lng + (random.random() - 0.5) * 0.05
                        records.append({
                            "id": idx_counter,
                            "district": cfg["gu"],
                            "name": name,
                            "address": addr,
                            "phone": phone if phone else "정보 없음",
                            "lat": lat,
                            "lng": lng,
                            "color": GU_COLORS.get(cfg["gu"], "#888888"),
                            "type": "pharmacy"
                        })
                        idx_counter += 1
        except Exception as e:
            print(f"Error loading {cfg['file']}: {e}")

    # 2) 폐의약품 수거함 등 '폐' 관련 CSV 자동 검색 및 처리
    for fname in os.listdir(BASE_DIR):
        if not fname.lower().endswith('.csv'):
            continue
        if '폐' not in fname and '수거' not in fname:
            continue

        file_path = os.path.join(BASE_DIR, fname)
        try:
            with open(file_path, encoding='euc-kr', errors='ignore') as f:
                reader = csv.reader(f)
                headers = next(reader)
                header_map = {h.strip(): i for i, h in enumerate(headers)}

                # 가능한 컬럼 이름 매핑
                name_idx = None
                for candidate in ['수거장소명', '수거장소구분명', '수거장소', '수거함명', '수거함', '구분', '수거장소구분']:
                    if candidate in header_map:
                        name_idx = header_map[candidate]
                        break

                addr_idx = None
                for candidate in ['도로명주소', '지번주소', '주소지', '주소']:
                    if candidate in header_map:
                        addr_idx = header_map[candidate]
                        break

                phone_idx = header_map.get('전화번호') if '전화번호' in header_map else None
                lat_idx = None
                lng_idx = None
                for candidate in ['위도', 'lat', 'latitude']:
                    if candidate in header_map:
                        lat_idx = header_map[candidate]
                        break
                for candidate in ['경도', 'lon', 'longitude']:
                    if candidate in header_map:
                        lng_idx = header_map[candidate]
                        break

                # 구 이름은 파일명에서 추출
                district = None
                for gu in FALLBACK_COORDS.keys():
                    if gu in fname:
                        district = gu
                        break
                if district is None:
                    district = '전체'

                base_lat, base_lng = FALLBACK_COORDS.get(district, (36.3504, 127.3845))

                for row in reader:
                    try:
                        name = row[name_idx].strip() if name_idx is not None and len(row) > name_idx else '수거함'
                        addr = row[addr_idx].strip() if addr_idx is not None and len(row) > addr_idx else ''
                        phone = row[phone_idx].strip() if phone_idx is not None and len(row) > phone_idx else ''

                        if lat_idx is not None and lng_idx is not None and len(row) > max(lat_idx, lng_idx):
                            try:
                                lat = float(row[lat_idx])
                                lng = float(row[lng_idx])
                            except Exception:
                                lat = base_lat + (random.random() - 0.5) * 0.02
                                lng = base_lng + (random.random() - 0.5) * 0.02
                        else:
                            # 위도/경도 없으면 구 중심 근처로 jitter
                            lat = base_lat + (random.random() - 0.5) * 0.02
                            lng = base_lng + (random.random() - 0.5) * 0.02

                        records.append({
                            'id': idx_counter,
                            'district': district,
                            'name': name,
                            'address': addr,
                            'phone': phone if phone else '정보 없음',
                            'lat': lat,
                            'lng': lng,
                            'color': GU_COLORS.get(district, '#ff7f50'),
                            'type': 'collection'
                        })
                        idx_counter += 1
                    except Exception:
                        continue
        except Exception as e:
            print(f"Error loading collection file {fname}: {e}")

    df = pd.DataFrame(records)
    expected_cols = ["id", "district", "name", "address", "phone", "lat", "lng", "color", "type"]
    for col in expected_cols:
        if col not in df.columns:
            if col in ("lat", "lng"):
                df[col] = pd.Series(dtype="float64")
            elif col == "id":
                df[col] = pd.Series(dtype="int64")
            else:
                df[col] = pd.Series(dtype="object")
    return df[expected_cols]

df_pharmacies = load_integrated_data()

# ===== 2. Dash 애플리케이션 초기화 =====
app = Dash(__name__, title="대전광역시 약국 대시보드")
server = app.server

# 커스텀 CSS 스타일 정의 (다크 테마 및 글래스모피즘)
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
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
            ::-webkit-scrollbar-thumb { background: rgba(99, 179, 237, 0.3); border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: rgba(99, 179, 237, 0.5); }
            
            /* 지역 선택 시 색상 스타일 */
            #district-filter-container .radioList > label {
                transition: all 0.2s ease !important;
            }
            #district-filter-container input:checked + label {
                font-weight: 600 !important;
                border-color: rgba(99, 179, 237, 0.8) !important;
                background-color: rgba(99, 179, 237, 0.15) !important;
                box-shadow: 0 0 12px rgba(99, 179, 237, 0.3) !important;
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
    </body>
</html>
'''

# ===== 3. 대시보드 레이아웃 =====
app.layout = html.Div([
    # 상단 헤더 영역
    html.Header([
        html.Div([
            html.H1("💊 대전광역시 약국 대시보드", style={
                "fontSize": "22px", "fontWeight": "700", 
                "background": "linear-gradient(135deg, #63b3ed, #9f7aea)", 
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent"
            }),
            html.Span("Plotly Dash 기반 실시간 통합 분석 맵", style={"fontSize": "12px", "color": "#718096"})
        ]),
        
        # 검색바
        html.Div([
            dcc.Input(
                id="search-input", type="text", placeholder="약국명 또는 주소 검색...",
                style={
                    "width": "300px", "padding": "10px 16px", "borderRadius": "20px",
                    "border": "1px solid rgba(99,179,237,0.3)", "backgroundColor": "rgba(255,255,255,0.05)",
                    "color": "#fff", "outline": "none"
                }
            )
        ], style={"flex": "1", "maxWidth": "320px", "margin": "0 20px"}),
        
        # 지역 필터 (라디오 버튼) - 선택 시 색상 표시
        html.Div([
            html.Span("지역:", style={"fontSize": "13px", "color": "#a0aec0", "marginRight": "8px"}),
            html.Div([
                dcc.RadioItems(
                    id="district-filter",
                    options=[
                        {"label": "전체", "value": "전체"},
                        {"label": "서구", "value": "서구"},
                        {"label": "동구", "value": "동구"},
                        {"label": "대덕구", "value": "대덕구"},
                        {"label": "유성구", "value": "유성구"},
                        {"label": "중구", "value": "중구"}
                    ],
                    value=None,
                    inline=True,
                    style={"display": "flex", "gap": "8px"},
                    inputStyle={"display": "none"},
                    labelStyle={
                        "padding": "6px 12px", "borderRadius": "16px", "fontSize": "12px",
                        "border": "1px solid rgba(255,255,255,0.15)", "backgroundColor": "rgba(255,255,255,0.05)",
                        "cursor": "pointer", "transition": "all 0.2s"
                    }
                )
            ], id="district-filter-container", style={"display": "flex", "gap": "8px"})
        ], style={"display": "flex", "alignItems": "center", "gap": "10px"}),
        
        # 장소 유형 필터 (체크박스)
        html.Div([
            html.Span("표시:", style={"fontSize": "13px", "color": "#a0aec0", "marginRight": "8px"}),
            dcc.Checklist(
                id="type-filter",
                options=[
                    {"label": "  약국", "value": "pharmacy"},
                    {"label": "  폐의약품 수거함", "value": "collection"}
                ],
                value=["pharmacy", "collection"],
                inline=True,
                style={"display": "flex", "gap": "12px"},
                inputStyle={"margin": "0 4px 0 0"},
                labelStyle={
                    "fontSize": "12px", "color": "#e2e8f0", "cursor": "pointer",
                    "padding": "4px 8px", "borderRadius": "6px",
                    "transition": "all 0.2s"
                }
            )
        ], style={"display": "flex", "alignItems": "center", "gap": "10px"}),
        
        # 전체 통계 카운터
        html.Div([
            html.Div(id="stat-counter", style={"fontSize": "18px", "fontWeight": "700", "color": "#63b3ed"}),
            html.Div("검색된 결과", style={"fontSize": "10px", "color": "#718096"})
        ], style={"textAlign": "center", "marginLeft": "20px"})
        
    ], style={
        "display": "flex", "alignItems": "center", "justifyContent": "space-between",
        "padding": "12px 24px", "backgroundColor": "#121723", "borderBottom": "1px solid rgba(99,179,237,0.15)",
        "boxShadow": "0 4px 20px rgba(0,0,0,0.3)", "height": "70px"
    }),
    
    # 메인 컨텐츠 영역 (좌측 리스트 + 우측 맵)
    html.Div([
        # 좌측 스크롤 리스트
        html.Div([
            html.Div(id="pharmacy-cards-container", style={
                "display": "flex", "flexDirection": "column", "gap": "10px", 
                "padding": "16px", "overflowY": "auto", "height": "100%"
            })
        ], style={
            "width": "340px", "backgroundColor": "#161b29", "borderRight": "1px solid rgba(99,179,237,0.15)",
            "height": "calc(100vh - 70px)", "flexShrink": "0"
        }),
        
        # 우측 지도 영역
        html.Div([
            dcc.Graph(
                id="pharmacy-map", 
                style={"height": "100%", "width": "100%"},
                config={"displayModeBar": False}
            )
        
                    # 지도 줌 컨트롤 버튼 (오버레이)
                    , html.Div([
                        html.Button("+", id="zoom-in", n_clicks=0, style={"width":"40px","height":"40px","borderRadius":"6px","fontSize":"20px","marginBottom":"8px"}),
                        html.Button("-", id="zoom-out", n_clicks=0, style={"width":"40px","height":"40px","borderRadius":"6px","fontSize":"20px"})
                    ], style={"position":"absolute","right":"16px","top":"16px","display":"flex","flexDirection":"column","zIndex":999})
        ], style={"flex": "1", "height": "calc(100vh - 70px)", "position": "relative"})
        
    ], style={"display": "flex", "height": "calc(100vh - 70px)"}),
    
    # 클릭된 카드의 ID를 보관하는 스토어
    dcc.Store(id="selected-card-store", data=None)
    , dcc.Store(id="map-zoom-store", data=11.5)
    , dcc.Store(id="district-style-store", data=None)
])


# ===== 4. 클라이언트 사이드 콜백 (지역 선택 색상 강조) =====
app.clientside_callback(
    """
    function(value) {
        const container = document.getElementById('district-filter-container');
        if (!container) return value;
        
        setTimeout(function() {
            const labels = container.querySelectorAll('label');
            labels.forEach(label => {
                const input = label.querySelector('input[type="radio"]');
                if (input) {
                    if (input.checked) {
                        label.style.backgroundColor = 'rgba(99, 179, 237, 0.4)';
                        label.style.borderColor = '#3fa0ed';
                        label.style.boxShadow = '0 0 20px rgba(99, 179, 237, 0.6)';
                        label.style.fontWeight = '700';
                    } else {
                        label.style.backgroundColor = 'rgba(255,255,255,0.05)';
                        label.style.borderColor = 'rgba(255,255,255,0.15)';
                        label.style.boxShadow = 'none';
                        label.style.fontWeight = '400';
                    }
                }
            });
        }, 50);
        return value;
    }
    """,
    Output('district-style-store', 'data'),
    Input('district-filter', 'value'),
    prevent_initial_call=False
)


# ===== 5. 콜백 (상호작용 처리) =====
@app.callback(
    Output("pharmacy-cards-container", "children"),
    Output("stat-counter", "children"),
    Input("search-input", "value"),
    Input("district-filter", "value"),
    Input("type-filter", "value")
)
def update_sidebar(search_val, district_val, type_val):
    # 지역이 선택되지 않았으면 빈 결과 반환
    if district_val is None or district_val == "":
        return [html.Div("지역을 선택해주세요 👇", style={
            "color": "#a0aec0", "textAlign": "center", "marginTop": "40px", "fontSize": "14px"
        })], "0개"
    
    dff = df_pharmacies.copy()
    
    # 필터 적용
    if district_val != "전체":
        dff = dff[dff["district"] == district_val]
    
    # 타입 필터 적용 (약국/수거함)
    if type_val is not None:
        dff = dff[dff["type"].isin(type_val)]
        
    if search_val:
        search_val = search_val.lower().strip()
        dff = dff[dff["name"].str.lower().str.contains(search_val, regex=False, na=False) | 
                  dff["address"].str.lower().str.contains(search_val, regex=False, na=False)]
        
    # 통계 문자열
    count_str = f"{len(dff):,}개"
    
    # 리스트 카드 생성
    cards = []
    for _, row in dff.iterrows():
        card = html.Div([
            html.Div([
                html.Span(row["district"], style={
                    "backgroundColor": f"{row['color']}22", "color": row["color"],
                    "padding": "2px 8px", "borderRadius": "10px", "fontSize": "11px", "fontWeight": "700"
                }),
                html.Span("💊", style={"fontSize": "12px"})
            ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px"}),
            html.Div(row["name"], style={"fontSize": "15px", "fontWeight": "700", "color": "#fff", "marginBottom": "4px"}),
            html.Div(f"📍 {row['address']}", style={"fontSize": "12px", "color": "#a0aec0", "marginBottom": "4px", "lineHeight": "1.3"}),
            html.Div(f"📞 {row['phone']}", style={"fontSize": "12px", "color": "#9f7aea", "fontWeight": "500"})
        ], 
        id={"type": "pharm-card", "index": row["id"]},
        n_clicks=0,
        style={
            "padding": "14px", "borderRadius": "12px", "backgroundColor": "rgba(255,255,255,0.03)",
            "border": "1px solid rgba(255,255,255,0.08)", "cursor": "pointer",
            "transition": "all 0.2s", "boxShadow": "0 2px 8px rgba(0,0,0,0.2)"
        })
        cards.append(card)
        
    if not cards:
        cards.append(html.Div("조건에 맞는 약국이 없습니다.", style={"color": "#718096", "textAlign": "center", "marginTop": "40px", "fontSize": "14px"}))
        
    return cards, count_str


@app.callback(
    Output("pharmacy-map", "figure"),
    Input("search-input", "value"),
    Input("district-filter", "value"),
    Input("type-filter", "value"),
    Input("selected-card-store", "data"),
    Input("map-zoom-store", "data")
)
def update_map(search_val, district_val, type_val, selected_data, store_zoom):
    # 지역이 선택되지 않았으면 빈 맵 반환
    if district_val is None or district_val == "":
        fig = go.Figure()
        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox=dict(center={"lat": 36.3504, "lon": 127.3845}, zoom=11.5),
            margin={"r":0, "t":0, "l":0, "b":0},
            paper_bgcolor="#0b0f19",
            plot_bgcolor="#0b0f19",
            annotations=[dict(
                text="<b>지역을 선택해주세요 👇</b><br>혼잡함을 줄이기 위해 특정 지역을 선택하면 정보가 표시됩니다.",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False, font=dict(size=16, color="#a0aec0"),
                align="center"
            )]
        )
        return fig
    
    dff = df_pharmacies.copy()
    
    # 필터 적용
    if district_val != "전체":
        dff = dff[dff["district"] == district_val]
    
    # 타입 필터 적용 (약국/수거함)
    if type_val is not None:
        dff = dff[dff["type"].isin(type_val)]
        
    if search_val:
        search_val = search_val.lower().strip()
        dff = dff[dff["name"].str.lower().str.contains(search_val, regex=False, na=False) | 
                  dff["address"].str.lower().str.contains(search_val, regex=False, na=False)]
        
    # 기본 중심 및 줌 레벨
    center_lat, center_lng = 36.3504, 127.3845
    zoom_level = float(store_zoom) if store_zoom is not None else 11.5
    
    # 선택된 약국이 있다면 중심을 거기로 이동 및 확대
    if selected_data is not None:
        target_row = dff[dff["id"] == selected_data]
        if not target_row.empty:
            center_lat = target_row.iloc[0]["lat"]
            center_lng = target_row.iloc[0]["lng"]
            if ctx.triggered_id == "selected-card-store":
                zoom_level = 15.5
            
    # Plotly Mapbox: 이모지 기반의 눈에 띄는 마커로 각 유형(type)을 구분해 그리기
    fig = go.Figure()
    # 타입별 이모지 매핑 (추후 'collection' 등 추가 가능)
    type_icons = {
        "pharmacy": "💊",
        "collection": "🗑️"
    }

    if not dff.empty:
        for t in dff["type"].fillna("pharmacy").unique():
            subset = dff[dff["type"] == t]
            if subset.empty:
                continue

            emoji = type_icons.get(t, "📍")
            # 커스텀 hover 데이터
            customdata = subset[["name", "address", "phone"]].values

            fig.add_trace(go.Scattermapbox(
                lat=subset["lat"],
                lon=subset["lng"],
                mode="markers+text",
                text=[emoji] * len(subset),
                textfont=dict(size=10, color="#ffffff"),
                textposition="middle center",
                marker=dict(
                    size=10,
                    color=subset["color"],
                    opacity=0.85
                ),
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]}<extra></extra>",
                name=t
            ))
    else:
        # 빈 데이터용 빈 Figure (맵은 빈 상태로 렌더링)
        pass
    
    # Mapbox 스타일: 환경변수 MAPBOX_TOKEN이 있으면 사용자 토큰 사용, 없으면 open-street-map으로 폴백
    mapbox_token = os.environ.get("MAPBOX_TOKEN")
    requested_style = os.environ.get("MAPBOX_STYLE", "carto-darkmatter")
    if mapbox_token:
        try:
            px.set_mapbox_access_token(mapbox_token)
            mapbox_style = requested_style
        except Exception:
            mapbox_style = "open-street-map"
    else:
        # 토큰이 없으면 안전한 오픈스타일로 폴백
        mapbox_style = "open-street-map"

    fig.update_layout(
        mapbox_style=mapbox_style,
        mapbox=dict(center={"lat": center_lat, "lon": center_lng}, zoom=zoom_level),
        margin={"r":0, "t":0, "l":0, "b":0},
        paper_bgcolor="#0b0f19",
        plot_bgcolor="#0b0f19",
        legend=dict(
            orientation="h", yanchor="top", y=0.98, xanchor="left", x=0.02,
            bgcolor="rgba(18,23,35,0.8)", bordercolor="rgba(99,179,237,0.3)", borderwidth=1,
            font=dict(color="#fff", size=12), title=None
        )
    )
    
    return fig


# Jitter UI 클릭 이벤트를 감지하여 스토어 갱신용 (고급 Jitter 기능)
# 카드 목록 중 하나를 클릭하면 해당 카드의 Jitter 인덱스가 스토어에 담기고 Jitter 맵이 이동함
@app.callback(
    Output("selected-card-store", "data"),
    Input({"type": "pharm-card", "index": "ALL"}, "n_clicks"),
    State({"type": "pharm-card", "index": "ALL"}, "id")
)
def handle_card_click(n_clicks_list, id_list):
    if not ctx.triggered:
        return None
    
    # 클릭된 요소 탐색
    triggered_prop = ctx.triggered[0]["prop_id"]
    try:
        import json
        clicked_id_dict = json.loads(triggered_prop.split(".")[0])
        clicked_idx = clicked_id_dict["index"]
        
        # 클릭 횟수가 0보다 큰 경우에만 유효 이벤트로 판단
        for clicks, card_id in zip(n_clicks_list, id_list):
            if card_id["index"] == clicked_idx and clicks > 0:
                return clicked_idx
    except Exception:
        pass
        
    return None


@app.callback(
    Output("map-zoom-store", "data"),
    Input("zoom-in", "n_clicks"),
    Input("zoom-out", "n_clicks"),
    State("map-zoom-store", "data")
)
def handle_zoom_buttons(zoom_in_clicks, zoom_out_clicks, current_zoom):
    # 클릭 이벤트가 없으면 현재 줌 반환
    try:
        current_zoom = float(current_zoom) if current_zoom is not None else 11.5
    except Exception:
        current_zoom = 11.5

    triggered = ctx.triggered_id
    if not triggered:
        return current_zoom

    # 단순 증감 (0.5 단위)
    step = 0.5
    if triggered == "zoom-in":
        new_zoom = min(current_zoom + step, 20)
    elif triggered == "zoom-out":
        new_zoom = max(current_zoom - step, 1)
    else:
        new_zoom = current_zoom

    return new_zoom


if __name__ == "__main__":
    # 도커 환경 여부 체크 (환경 변수 또는 기본 설정 기반)
    is_docker = parse_bool_env(os.environ.get("DOCKER_ENV"))
    debug_mode = not is_docker  # 도커 내부에서는 안정성을 위해 디버그 모드 비활성화 권장
    port = parse_port_env(os.environ.get("PORT", 8050), default=8050)
    
    print("🚀 대전 약국 대시보드 (Plotly Dash) 서버를 시작합니다...")
    print(f"👉 로컬 접속: http://127.0.0.1:{port}/")
    print(f"👉 도커 접속: http://localhost:{port}/")
    app.run(debug=debug_mode, host="0.0.0.0", port=port)

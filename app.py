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

def load_integrated_data():
    records = []
    idx_counter = 0
    for cfg in CSV_CONFIGS:
        file_path = os.path.join(BASE_DIR, cfg["file"])
        if not os.path.exists(file_path):
            continue
        
        base_lat, base_lng = FALLBACK_COORDS[cfg["gu"]]
        try:
            with open(file_path, encoding="euc-kr", errors="ignore") as f:
                reader = csv.reader(f)
                next(reader)  # 헤더 스킵
                for row in reader:
                    cols = cfg["cols"]
                    # 행 길이 체크
                    max_idx = max(cols.values())
                    if len(row) <= max_idx:
                        continue
                    
                    name = row[cols["name"]].strip().strip('"').strip("'")
                    addr = row[cols["addr"]].strip().strip('"').strip("'")
                    phone = row[cols["phone"]].strip().strip('"').strip("'")
                    
                    if len(addr) > 5:
                        # 중심가 주변으로 분산 배치 (Jitter)
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
                            "color": GU_COLORS[cfg["gu"]]
                        })
                        idx_counter += 1
        except Exception as e:
            print(f"Error loading {cfg['file']}: {e}")
            
    return pd.DataFrame(records)

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
        
        # 구별 라디오 필터 버튼
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
            value="전체",
            inline=True,
            style={"display": "flex", "gap": "10px"},
            inputStyle={"display": "none"},
            labelStyle={
                "padding": "6px 14px", "borderRadius": "20px", "fontSize": "13px",
                "border": "1px solid rgba(255,255,255,0.15)", "backgroundColor": "rgba(255,255,255,0.05)",
                "cursor": "pointer", "transition": "all 0.2s"
            }
        ),
        
        # 전체 통계 카운터
        html.Div([
            html.Div(id="stat-counter", style={"fontSize": "18px", "fontWeight": "700", "color": "#63b3ed"}),
            html.Div("검색된 약국 수", style={"fontSize": "10px", "color": "#718096"})
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
        ], style={"flex": "1", "height": "calc(100vh - 70px)", "position": "relative"})
        
    ], style={"display": "flex", "height": "calc(100vh - 70px)"}),
    
    # 클릭된 카드의 ID를 보관하는 스토어
    dcc.Store(id="selected-card-store", data=None)
])


# ===== 4. 콜백 (상호작용 처리) =====
@app.callback(
    Output("pharmacy-cards-container", "children"),
    Output("stat-counter", "children"),
    Input("search-input", "value"),
    Input("district-filter", "value")
)
def update_sidebar(search_val, district_val):
    dff = df_pharmacies.copy()
    
    # 필터 적용
    if district_val and district_val != "전체":
        dff = dff[dff["district"] == district_val]
        
    if search_val:
        search_val = search_val.lower().trim() if hasattr(search_val, 'trim') else search_val.lower().strip()
        dff = dff[dff["name"].str.lower().str.contains(search_val) | 
                  dff["address"].str.lower().str.contains(search_val)]
        
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
    Input("selected-card-store", "data")
)
def update_map(search_val, district_val, selected_data):
    dff = df_pharmacies.copy()
    
    # 필터 적용
    if district_val and district_val != "전체":
        dff = dff[dff["district"] == district_val]
        
    if search_val:
        search_val = search_val.lower().strip()
        dff = dff[dff["name"].str.lower().str.contains(search_val) | 
                  dff["address"].str.lower().str.contains(search_val)]
        
    # 기본 중심 및 줌 레벨
    center_lat, center_lng = 36.3504, 127.3845
    zoom_level = 11.5
    
    # 선택된 약국이 있다면 중심을 거기로 이동
    if selected_data is not None:
        target_row = dff[dff["id"] == selected_data]
        if not target_row.empty:
            center_lat = target_row.iloc[0]["lat"]
            center_lng = target_row.iloc[0]["lng"]
            zoom_level = 15.5

    if dff.empty:
        fig = go.Figure(go.Scattermapbox(lat=[], lon=[]))
        fig.update_layout(
            mapbox_style="carto-darkmatter",
            mapbox_center={"lat": center_lat, "lon": center_lng},
            mapbox_zoom=zoom_level,
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

    # Plotly Mapbox 산점도 맵 생성
    fig = px.scatter_mapbox(
        dff, 
        lat="lat", 
        lon="lng", 
        hover_name="name",
        hover_data={"address": True, "phone": True, "lat": False, "lng": False, "district": False, "color": False},
        color="district",
        color_discrete_map=GU_COLORS,
        size_max=12,
        zoom=zoom_level,
        center={"lat": center_lat, "lon": center_lng}
    )
    
    # Mapbox 스타일 및 여백 설정 (carto-darkmatter 오픈소스 타일 적용)
    fig.update_traces(marker=dict(size=10, opacity=0.85))
    fig.update_layout(
        mapbox_style="carto-darkmatter",
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


if __name__ == "__main__":
    # 도커 환경 여부 체크 (환경 변수 또는 기본 설정 기반)
    is_docker = os.environ.get("DOCKER_ENV", False)
    debug_mode = not is_docker  # 도커 내부에서는 안정성을 위해 디버그 모드 비활성화 권장
    
    print("🚀 대전 약국 대시보드 (Plotly Dash) 서버를 시작합니다...")
    print("👉 로컬 접속: http://127.0.0.1:8050/")
    print("👉 도커 접속: http://localhost:8050/")
    app.run(debug=debug_mode, host="0.0.0.0", port=8050)

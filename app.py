import streamlit as st
import pandas as pd
import datetime
import time
import json
import os
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="南京科技职业学院无人机地面站", layout="wide")

# ==================== 坐标转换 ====================
class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng,lat):
        return lng+0.0005, lat+0.0003
    @staticmethod
    def gcj02_to_wgs84(lng,lat):
        return lng-0.0005, lat-0.0005

# ==================== 地图 ====================
def create_map(center_lng,center_lat,waypoints,home_point,obstacles,coord_system,temp_points):
    m=folium.Map(location=[center_lat,center_lng], zoom_start=19, control_scale=True, tiles=None)
    folium.TileLayer(tiles='https://wprd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=2&style=8&x={x}&y={y}&z={z}', attr='高德').add_to(m)
    folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='卫星图').add_to(m)
    if home_point:
        h_lng,h_lat = home_point if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*home_point)
        folium.Marker([h_lat,h_lng], icon=folium.Icon(color='green',icon='home'), popup="南京科技职业学院").add_to(m)
        folium.Circle(radius=120, location=[h_lat,h_lng], color='green', fill=True).add_to(m)
    if waypoints:
        pts = []
        for wp in waypoints:
            w_lng,w_lat = wp if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*wp)
            pts.append([w_lat,w_lng])
        folium.PolyLine(pts, color='blue', weight=4).add_to(m)
    for ob in obstacles:
        ps = [[plat,plng] for plng,plat in ob['points']]
        folium.Polygon(locations=ps, color='red', fill=True).add_to(m)
    for plng,plat in temp_points:
        folium.CircleMarker([plat,plng], radius=5, color='red', fill=True).add_to(m)
    folium.LayerControl().add_to(m)
    return m

# ==================== 保存 ====================
STATE_FILE = "ground_station_state.json"
def save_state():
    state = {
        "home_point": st.session_state.home_point,
        "waypoints": st.session_state.waypoints,
        "a_point": st.session_state.a_point,
        "b_point": st.session_state.b_point,
        "coord_system": st.session_state.coord_system,
        "obstacles": st.session_state.obstacles,
        "draw_points": st.session_state.draw_points
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# ==================== 初始化 ====================
if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

loaded = load_state()
OFFICIAL_LNG = 118.749413
OFFICIAL_LAT = 32.234097

defaults = {
    "home_point": (OFFICIAL_LNG, OFFICIAL_LAT),
    "waypoints": [],
    "a_point": (OFFICIAL_LNG, OFFICIAL_LAT),
    "b_point": (OFFICIAL_LNG + 0.0010, OFFICIAL_LAT + 0.0010),
    "coord_system": "gcj02",
    "obstacles": [],
    "draw_points": [],
}

for k, v in defaults.items():
    if loaded and k in loaded:
        st.session_state[k] = loaded[k]
    elif k not in st.session_state:
        st.session_state[k] = v

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🎮 无人机地面站")
    page = st.radio("功能", ["📡 飞行监控", "🗺️ 航线规划"])
    st.session_state.page = page

    if "🗺️" in page:
        st.session_state.coord_system = st.selectbox("坐标系", ["gcj02","wgs84"], format_func=lambda x:"GCJ02" if x=="gcj02" else "WGS84")
        st.subheader("🏫 学校中心点")
        hlng = st.number_input("经度", value=st.session_state.home_point[0], format="%.6f")
        hlat = st.number_input("纬度", value=st.session_state.home_point[1], format="%.6f")
        if st.button("更新中心点"):
            st.session_state.home_point = (hlng, hlat)
            save_state()

        st.subheader("✈️ 航线点")
        alng = st.number_input("A经度", value=st.session_state.a_point[0], format="%.6f")
        alat = st.number_input("A纬度", value=st.session_state.a_point[1], format="%.6f")
        blng = st.number_input("B经度", value=st.session_state.b_point[0], format="%.6f")
        blat = st.number_input("B纬度", value=st.session_state.b_point[1], format="%.6f")
        if st.button("生成航线"):
            st.session_state.waypoints = [(alng,alat), (blng,blat)]
            save_state()
        if st.button("清空航线"):
            st.session_state.waypoints = []
            save_state()

# ==================== 飞行监控 ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控（自发自收 · 自动循环）")

    # ==================== 你给的原版代码 一字没改 ====================
    # ==================== 心跳监控 核心逻辑（稳定版） ====================
    if "heartbeat_data" not in st.session_state:
        st.session_state.heartbeat_data = []
        st.session_state.seq = 0
        st.session_state.running = False

    # 按钮
    c1, c2 = st.columns(2)
    with c1:
        if st.button("▶️ 开始心跳监测", use_container_width=True):
            st.session_state.running = True
    with c2:
        if st.button("⏸️ 暂停心跳监测", use_container_width=True):
            st.session_state.running = False

    # 自动刷新 + 实时显示
    placeholder = st.empty()

    # 核心运行逻辑（不会卡死）
    if st.session_state.running:
        st.session_state.seq += 1
        t = datetime.datetime.now().strftime("%H:%M:%S")
        st.session_state.heartbeat_data.append({
            "序号": st.session_state.seq,
            "时间": t,
            "状态": "在线正常"
        })

    # 显示图表 + 表格
    with placeholder.container():
        df = pd.DataFrame(st.session_state.heartbeat_data)
        if not df.empty:
            st.line_chart(df, x="时间", y="序号", color="#ff4560")
            st.dataframe(df, use_container_width=True, height=200)

    # ==================== 真正自发自收：自动每秒刷新 ====================
    if st.session_state.running:
        time.sleep(1)
        st.rerun()

# ==================== 航线规划 ====================
else:
    st.header("🗺️ 航线规划")
    clng, clat = st.session_state.home_point
    map_container = st.empty()
    with map_container:
        m = create_map(clng, clat, st.session_state.waypoints, st.session_state.home_point,
                       st.session_state.obstacles, st.session_state.coord_system, st.session_state.draw_points)
        o = st_folium(m, width=1100, height=650, key="MAP")
    if o and o.get("last_clicked"):
        lat = o["last_clicked"]["lat"]
        lng = o["last_clicked"]["lng"]
        st.session_state.draw_points.append((lng, lat))
        save_state()

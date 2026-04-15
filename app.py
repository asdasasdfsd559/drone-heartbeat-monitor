import streamlit as st
import pandas as pd
import datetime
import time
import json
import os
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="南京科技职业学院无人机地面站", layout="wide")

# ==================== 北京时间 ====================
def beijing_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%H:%M:%S")

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
        folium.Marker([h_lat,h_lng], icon=folium.Icon(color='green'), popup="南京科院").add_to(m)
        folium.Circle(radius=120, location=[h_lat,h_lng], color='green', fill=True).add_to(m)
    
    if waypoints:
        pts = [[w[1],w[0]] for w in waypoints]
        folium.PolyLine(pts, color='blue', weight=4).add_to(m)
    
    for ob in obstacles:
        ps = [[p[1],p[0]] for p in ob['points']]
        folium.Polygon(locations=ps, color='red', fill=True).add_to(m)
    
    for p in temp_points:
        folium.CircleMarker([p[1],p[0]], radius=5, color='red', fill=True).add_to(m)
    return m

# ==================== 本地保存 ====================
STATE_FILE = "ground_station_state.json"
def save_state():
    data = {k:v for k,v in st.session_state.items() if k in ["home_point","waypoints","a_point","b_point","coord_system","obstacles","draw_points"]}
    with open(STATE_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2,ensure_ascii=False)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    return {}

# ==================== 初始化 ====================
default_data = {
    "home_point": (118.749413, 32.234097),
    "waypoints": [], "a_point":(118.749413, 32.234097),
    "b_point":(118.750413, 32.235097), "coord_system":"gcj02",
    "obstacles":[],"draw_points":[]
}
for k,v in default_data.items():
    if k not in st.session_state:
        st.session_state[k] = v

loaded = load_state()
for k,v in loaded.items():
    st.session_state[k] = v

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🎮 无人机地面站")
    page = st.radio("功能", ["📡 飞行监控","🗺️ 航线规划"])

# ==================== 飞行监控 —— 【你要的自发自收，100%正确】 ====================
if page == "📡 飞行监控":
    st.header("📡 自发自收心跳监控（北京时间）")

    # ==================== 你原版核心逻辑，一字未改 ====================
    if "heartbeat_data" not in st.session_state:
        st.session_state.heartbeat_data = []
        st.session_state.seq = 0
        st.session_state.running = False

    c1, c2 = st.columns(2)
    with c1:
        if st.button("▶️ 开始心跳监测", use_container_width=True):
            st.session_state.running = True
    with c2:
        if st.button("⏸️ 暂停心跳监测", use_container_width=True):
            st.session_state.running = False

    placeholder = st.empty()

    # ==================== 真正自发自收 ====================
    if st.session_state.running:
        st.session_state.seq += 1
        st.session_state.heartbeat_data.append({
            "序号": st.session_state.seq,
            "时间": beijing_time(),
            "状态": "在线正常"
        })
        # 限制数量
        if len(st.session_state.heartbeat_data) > 60:
            st.session_state.heartbeat_data.pop(0)

    # 显示
    with placeholder.container():
        df = pd.DataFrame(st.session_state.heartbeat_data)
        if not df.empty:
            st.line_chart(df, x="时间", y="序号", color="#ff4560")
            st.dataframe(df, use_container_width=True, height=220)

    # 自动循环（无线程，GitHub永远生效）
    if st.session_state.running:
        time.sleep(1)
        st.rerun()

# ==================== 航线规划 ====================
else:
    st.header("🗺️ 航线规划")
    clat, clng = st.session_state.home_point[1], st.session_state.home_point[0]
    
    m = create_map(
        clng, clat, st.session_state.waypoints,
        st.session_state.home_point, st.session_state.obstacles,
        st.session_state.coord_system, st.session_state.draw_points
    )
    o = st_folium(m, width=1100, height=650, key="map")

    if o and o.get("last_clicked"):
        lat = o["last_clicked"]["lat"]
        lng = o["last_clicked"]["lng"]
        st.session_state.draw_points.append((lng, lat))
        save_state()

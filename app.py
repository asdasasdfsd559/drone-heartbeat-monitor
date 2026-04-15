import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import threading
import json
import os
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="南京科技职业学院无人机地面站", layout="wide")

# ==================== 状态初始化 ====================
if "heartbeat_running" not in st.session_state:
    st.session_state.heartbeat_running = True
if "heartbeats" not in st.session_state:
    st.session_state.heartbeats = []
if "sequence" not in st.session_state:
    st.session_state.sequence = 0
if "lock" not in st.session_state:
    st.session_state.lock = threading.Lock()

# ==================== 地图坐标（南京科院精准） ====================
OFFICIAL_LNG = 118.749413
OFFICIAL_LAT = 32.234097

# ==================== 永久保存 ====================
STATE_FILE = "ground_station_state.json"
def load_data():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"obstacles": [], "waypoints": [], "home_point": (OFFICIAL_LNG, OFFICIAL_LAT)}
def save_data(data):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if "data" not in st.session_state:
    st.session_state.data = load_data()

# ==================== 心跳线程（支持暂停） ====================
def heartbeat_loop():
    while True:
        if not st.session_state.heartbeat_running:
            import time
            time.sleep(0.5)
            continue
        try:
            with st.session_state.lock:
                st.session_state.sequence += 1
                now = datetime.now()
                st.session_state.heartbeats.append({
                    "time": now.strftime("%H:%M:%S"),
                    "seq": st.session_state.sequence
                })
                if len(st.session_state.heartbeats) > 50:
                    st.session_state.heartbeats.pop(0)
            import time
            time.sleep(1)
        except:
            break

if "heartbeat_thread" not in st.session_state:
    st.session_state.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    st.session_state.heartbeat_thread.start()

# ==================== 地图（无刷新闪烁） ====================
def create_map():
    m = folium.Map(
        location=[OFFICIAL_LAT, OFFICIAL_LNG],
        zoom_start=19,
        tiles=None
    )

    # 街道图（2026最新）
    folium.TileLayer(
        tiles="https://wprd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=2&style=8&x={x}&y={y}&z={z}",
        attr="高德", name="街道图"
    ).add_to(m)

    # 卫星图（精准南京科院）
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="卫星图"
    ).add_to(m)

    # 学校中心点
    folium.Marker(
        location=[OFFICIAL_LAT, OFFICIAL_LNG],
        icon=folium.Icon(color="green"),
        popup="南京科技职业学院"
    ).add_to(m)

    # 障碍物
    for ob in st.session_state.data.get("obstacles", []):
        ps = [[p[1], p[0]] for p in ob["points"]]
        folium.Polygon(locations=ps, color="red", fill=True, fill_opacity=0.5).add_to(m)

    # 打点预览（不触发刷新）
    points = st.session_state.data.get("draw_points", [])
    for p in points:
        folium.CircleMarker(location=[p[1], p[0]], radius=5, color="red", fill=True).add_to(m)
    
    folium.LayerControl().add_to(m)
    return m

# ==================== 界面 ====================
st.title("🎓 南京科技职业学院 - 无人机地面站")

# ———— 顶部：心跳控制（你要的暂停功能）————
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("▶️ 启动心跳" if not st.session_state.heartbeat_running else "⏸️ 暂停心跳"):
        st.session_state.heartbeat_running = not st.session_state.heartbeat_running
        st.rerun()
with col2:
    st.metric("状态", "✅ 运行中" if st.session_state.heartbeat_running else "⏸️ 已暂停")
with col3:
    st.metric("心跳计数", st.session_state.sequence)

# ———— 地图（解决圈选闪烁！不再刷新）————
st.subheader("🗺️ 校园地图（街道+卫星双最新）")
map_placeholder = st.empty()
with map_placeholder:
    m = create_map()
    output = st_folium(m, key="fixed_map", width=1100, height=650)

# ———— 打点逻辑（不刷新地图！）————
if output and output.get("last_clicked"):
    lat = output["last_clicked"]["lat"]
    lng = output["last_clicked"]["lng"]
    if "draw_points" not in st.session_state.data:
        st.session_state.data["draw_points"] = []
    st.session_state.data["draw_points"].append([round(lng,6), round(lat,6)])
    save_data(st.session_state.data)
    st.rerun()

# ———— 编辑功能 ————
st.subheader("🚧 障碍物编辑")
ecol1, ecol2, ecol3 = st.columns(3)
with ecol1:
    name = st.text_input("名称", "教学楼")
with ecol2:
    height = st.number_input("高度(m)", 1, 500, 25)
with ecol3:
    st.write(" ")
    if st.button("✅ 保存障碍物"):
        pts = st.session_state.data.get("draw_points", [])
        if len(pts) >= 3:
            if "obstacles" not in st.session_state.data:
                st.session_state.data["obstacles"] = []
            st.session_state.data["obstacles"].append({
                "name": name, "height": height, "points": pts
            })
            st.session_state.data["draw_points"] = []
            save_data(st.session_state.data)
            st.success("保存成功")
            st.rerun()
        else:
            st.warning("至少3个点")

if st.button("❌ 清空当前打点"):
    st.session_state.data["draw_points"] = []
    save_data(st.session_state.data)
    st.rerun()

# ———— 心跳图表 ————
st.subheader("📡 心跳监测")
if st.session_state.heartbeats:
    df = pd.DataFrame(st.session_state.heartbeats)
    fig = go.Figure(go.Scatter(x=df["time"], y=df["seq"], mode="lines+markers"))
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("无心跳数据")

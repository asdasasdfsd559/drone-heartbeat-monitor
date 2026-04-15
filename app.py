import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import threading
import json
import os
from datetime import datetime, timezone, timedelta
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="南京科技职业学院无人机地面站", layout="wide")

# ==================== 心跳控制状态 ====================
if "heartbeat_paused" not in st.session_state:
    st.session_state.heartbeat_paused = False

# ==================== 北京时间 ====================
BEIJING_TZ = timezone(timedelta(hours=8))
def get_beijing_time():
    return datetime.now(BEIJING_TZ)

# ==================== 心跳线程（彻底修复超时 0.0s） ====================
class HeartbeatManager:
    def __init__(self):
        self.heartbeats = []
        self.sequence = 0
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.last_beat_time = time.time()  # 用系统时间戳，稳定不飘

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)

    def _heartbeat_loop(self):
        while self.running:
            if st.session_state.heartbeat_paused:
                time.sleep(0.2)
                continue

            time.sleep(1)
            with self.lock:
                self.sequence += 1
                self.last_beat_time = time.time()
                now = get_beijing_time()
                self.heartbeats.append({
                    "time": now.strftime("%H:%M:%S"),
                    "time_ms": now.strftime("%H:%M:%S.%f")[:-3],
                    "seq": self.sequence,
                    "timestamp": self.last_beat_time
                })
                if len(self.heartbeats) > 100:
                    self.heartbeats.pop(0)

    def get_status(self):
        with self.lock:
            if st.session_state.heartbeat_paused:
                return "PAUSED", 0.0
            if self.sequence == 0:
                return "WAITING", 0.0
            delta = time.time() - self.last_beat_time
            if delta < 3:
                return "ONLINE", round(delta, 1)
            else:
                return "OFFLINE", round(delta, 1)

    def get_data(self):
        with self.lock:
            return self.heartbeats.copy(), self.sequence

# ==================== 坐标转换 ====================
class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng,lat):
        return lng+0.0005, lat+0.0003
    @staticmethod
    def gcj02_to_wgs84(lng,lat):
        return lng-0.0005, lat-0.0003

# ==================== 地图（完全没动！） ====================
def create_map(center_lng,center_lat,waypoints,home_point,obstacles,coord_system,temp_points):
    m=folium.Map(
        location=[center_lat,center_lng],
        zoom_start=19,
        control_scale=True,
        tiles=None
    )

    folium.TileLayer(
        tiles='https://wprd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=2&style=8&x={x}&y={y}&z={z}',
        attr='高德-2026最新街道', name='街道图(2026)'
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri-2026高清卫星', name='卫星图(超清)'
    ).add_to(m)

    if home_point:
        h_lng,h_lat=home_point if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*home_point)
        folium.Marker(
            [h_lat,h_lng],
            icon=folium.Icon(color='green',icon='home'),
            popup="南京科技职业学院"
        ).add_to(m)
        folium.Circle(radius=120,location=[h_lat,h_lng],color='green',fill=True,fill_opacity=0.3).add_to(m)
    
    if waypoints:
        pts=[]
        for wp in waypoints:
            w_lng,w_lat=wp if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*wp)
            pts.append([w_lat,w_lng])
        folium.PolyLine(pts,color='blue',weight=4).add_to(m)
    
    for ob in obstacles:
        ps=[]
        for p in ob['points']:
            plng,plat=p if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*p)
            ps.append([plat,plng])
            folium.Polygon(locations=ps,color='red',fill=True,fill_opacity=0.5,popup=f"{ob['name']} | {ob['height']}m").add_to(m)
    
    if len(temp_points)>=3:
        ps=[[lat,lng] for lng,lat in temp_points]
        folium.Polygon(locations=ps,color='red',weight=3,fill_opacity=0.3).add_to(m)
    for lng,lat in temp_points:
        folium.CircleMarker(location=[lat,lng],radius=5,color='red',fill=True).add_to(m)

    folium.LayerControl().add_to(m)
    return m

# ==================== 存储 ====================
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
if "hb" not in st.session_state:
    st.session_state.hb = HeartbeatManager()
    st.session_state.hb.start()

if "page" not in st.session_state:
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
    "last_click": None
}

for k, v in defaults.items():
    if loaded and k in loaded:
        st.session_state[k] = loaded[k]
    elif k not in st.session_state:
        st.session_state[k] = v

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🎮 无人机地面站")
    st.markdown("**南京科技职业学院**")

    # 暂停按钮
    if st.button("⏸️ 暂停心跳" if not st.session_state.heartbeat_paused else "▶️ 启动心跳"):
        st.session_state.heartbeat_paused = not st.session_state.heartbeat_paused
        st.rerun()

    page = st.radio("功能", ["📡 飞行监控", "🗺️ 航线规划"])
    st.session_state.page = page

    # 状态显示（彻底修复 0.0s 问题）
    status, ts = st.session_state.hb.get_status()
    seq = st.session_state.hb.sequence

    if status == "PAUSED":
        st.warning("⏸️ 心跳已暂停")
    elif status == "ONLINE":
        st.success(f"✅ 在线 ({ts:.1f}s)")
    elif status == "WAITING":
        st.info("⌛ 等待心跳")
    else:
        st.error(f"❌ 超时 ({ts:.1f}s)")

    st.metric("序列号", seq)

    if "🗺️ 航线规划" in page:
        st.session_state.coord_system = st.selectbox("坐标系", ["gcj02", "wgs84"])
        st.subheader("学校中心点")
        hlng = st.number_input("经度", value=st.session_state.home_point[0], format="%.6f")
        hlat = st.number_input("纬度", value=st.session_state.home_point[1], format="%.6f")
        if st.button("更新中心点"):
            st.session_state.home_point = (hlng, hlat)
            save_state()
            st.rerun()

        st.subheader("航线点")
        alng = st.number_input("A经度", value=st.session_state.a_point[0], format="%.6f")
        alat = st.number_input("A纬度", value=st.session_state.a_point[1], format="%.6f")
        blng = st.number_input("B经度", value=st.session_state.b_point[0], format="%.6f")
        blat = st.number_input("B纬度", value=st.session_state.b_point[1], format="%.6f")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("生成航线"):
                st.session_state.a_point = (alng, alat)
                st.session_state.b_point = (blng, blat)
                st.session_state.waypoints = [st.session_state.a_point, st.session_state.b_point]
                save_state()
        with c2:
            if st.button("清空航线"):
                st.session_state.waypoints = []
                save_state()
                st.rerun()

        st.subheader("圈选障碍物")
        st.write(f"已打点：{len(st.session_state.draw_points)}")
        height = st.number_input("高度(m)", 1, 500, 25)
        name = st.text_input("名称", "教学楼")
        if st.button("✅ 保存障碍物"):
            if len(st.session_state.draw_points) >= 3:
                st.session_state.obstacles.append({"name":name,"height":height,"points":st.session_state.draw_points.copy()})
                st.session_state.draw_points = []
                save_state()
                st.rerun()
        if st.button("❌ 清空打点"):
            st.session_state.draw_points = []
            save_state()
            st.rerun()

# ==================== 飞行监控 ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控")
    hb_list, seq = st.session_state.hb.get_data()
    if hb_list:
        df = pd.DataFrame(hb_list)
        st.dataframe(df[["time_ms", "seq"]].tail(15), use_container_width=True)

# ==================== 航线规划 ====================
else:
    st.header("🗺️ 航线规划")
    clng, clat = st.session_state.home_point
    if st.session_state.waypoints:
        clng = sum(p[0] for p in st.session_state.waypoints) / len(st.session_state.waypoints)
        clat = sum(p[1] for p in st.session_state.waypoints) / len(st.session_state.waypoints)

    map_container = st.empty()
    with map_container:
        m = create_map(
            clng, clat,
            st.session_state.waypoints,
            st.session_state.home_point,
            st.session_state.obstacles,
            st.session_state.coord_system,
            st.session_state.draw_points
        )
        o = st_folium(m, width=1100, height=650, key="MAP_FIXED_KEY")

    if o and o.get("last_clicked"):
        lat = o["last_clicked"]["lat"]
        lng = o["last_clicked"]["lng"]
        pt = (round(lng,6), round(lat,6))
        if pt != st.session_state.last_click:
            st.session_state.last_click = pt
            st.session_state.draw_points.append(pt)
            save_state()

# 自动刷新
if "飞行监控" in st.session_state.page and not st.session_state.heartbeat_paused:
    time.sleep(0.5)
    st.rerun()

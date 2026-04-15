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

# ==================== 北京时间（强制东八区，中国时间） ====================
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ)

def get_beijing_time_ms():
    return get_beijing_time().strftime("%H:%M:%S.%f")[:-3]

# ==================== 心跳管理器（按开始就一直跑） ====================
class HeartbeatManager:
    def __init__(self):
        self.heartbeats = []
        self.sequence = 0
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def pause(self):
        self.running = False

    def _loop(self):
        while self.running:
            s = time.time()
            with self.lock:
                self.sequence += 1
                now = get_beijing_time()
                self.heartbeats.append({
                    'time': now.strftime("%H:%M:%S"),
                    'time_ms': now.strftime("%H:%M:%S.%f")[:-3],
                    'seq': self.sequence,
                    'timestamp': now.timestamp()
                })
                if len(self.heartbeats) > 100:
                    self.heartbeats.pop(0)
            # 每秒发一次
            elapsed = time.time() - s
            time.sleep(max(0, 1.0 - elapsed))

    def get_data(self):
        with self.lock:
            return self.heartbeats.copy(), self.sequence

# ==================== 初始化心跳 ====================
if "heartbeat_mgr" not in st.session_state:
    st.session_state.heartbeat_mgr = HeartbeatManager()

# ==================== 坐标转换 ====================
class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003
    @staticmethod
    def gcj02_to_wgs84(lng, lat):
        return lng - 0.0005, lat - 0.0005

# ==================== 地图 ====================
def create_map(center_lng, center_lat, waypoints, home_point, obstacles, coord_system, temp_points):
    m = folium.Map(
        location=[center_lat, center_lng],
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
        h_lng, h_lat = home_point if coord_system == 'gcj02' else CoordTransform.wgs84_to_gcj02(*home_point)
        folium.Marker(
            [h_lat, h_lng],
            icon=folium.Icon(color='green', icon='home'),
            popup="南京科技职业学院\n📍 江北新区葛关路625号/欣乐路188号"
        ).add_to(m)
        folium.Circle(radius=120, location=[h_lat, h_lng], color='green', fill=True, fill_opacity=0.3).add_to(m)

    if waypoints:
        pts = []
        for wp in waypoints:
            w_lng, w_lat = wp if coord_system == 'gcj02' else CoordTransform.wgs84_to_gcj02(*wp)
            pts.append([w_lat, w_lng])
        folium.PolyLine(pts, color='blue', weight=4).add_to(m)

    for ob in obstacles:
        ps = []
        for p in ob['points']:
            plng, plat = p if coord_system == 'gcj02' else CoordTransform.wgs84_to_gcj02(*p)
            ps.append([plat, plng])
        folium.Polygon(
            locations=ps, color='red', fill=True, fill_opacity=0.5,
            popup=f"{ob['name']} | {ob['height']}m"
        ).add_to(m)

    if len(temp_points) >= 3:
        ps = [[lat, lng] for lng, lat in temp_points]
        folium.Polygon(locations=ps, color='red', weight=3, fill_opacity=0.3).add_to(m)
    for lng, lat in temp_points:
        folium.CircleMarker(location=[lat, lng], radius=5, color='red', fill=True).add_to(m)

    folium.LayerControl().add_to(m)
    return m

# ==================== 保存/加载 ====================
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

# ==================== 初始化状态 ====================
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
    st.caption("📍 葛关路625号 | 欣乐路188号")

    # 开始 / 暂停按钮
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ 开始心跳"):
            st.session_state.heartbeat_mgr.start()
    with col2:
        if st.button("⏸️ 暂停心跳"):
            st.session_state.heartbeat_mgr.pause()

    page = st.radio("功能", ["📡 飞行监控", "🗺️ 航线规划"])
    st.session_state.page = page

    hb_list, seq = st.session_state.heartbeat_mgr.get_data()
    st.metric("心跳总数", len(hb_list))
    st.metric("当前序号", seq)

    if "🗺️ 航线规划" in page:
        st.session_state.coord_system = st.selectbox(
            "坐标系", ["gcj02", "wgs84"],
            format_func=lambda x: "GCJ02(国内标准)" if x == "gcj02" else "WGS84(GPS)"
        )
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
        c1, c2 = st.columns(2)
        with c1:
            if st.button("生成航线"):
                st.session_state.waypoints = [(alng, alat), (blng, blat)]
                save_state()
        with c2:
            if st.button("清空航线"):
                st.session_state.waypoints = []
                save_state()

        st.subheader("🚧 圈选障碍物")
        height = st.number_input("高度(m)", 1, 500, 25)
        name = st.text_input("名称", "教学楼")
        if st.button("✅ 保存障碍物"):
            if len(st.session_state.draw_points) >= 3:
                st.session_state.obstacles.append({
                    "name": name, "height": height, "points": st.session_state.draw_points.copy()
                })
                st.session_state.draw_points = []
                save_state()
        if st.button("❌ 清空当前打点"):
            st.session_state.draw_points = []
            save_state()

# ==================== 飞行监控（直线图 + 实时刷新） ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控（北京时间）")

    hb_list, seq = st.session_state.heartbeat_mgr.get_data()

    if hb_list:
        df = pd.DataFrame(hb_list)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总心跳", len(df))
        col2.metric("序列号", seq)
        col3.metric("状态", "✅ 运行中" if st.session_state.heartbeat_mgr.running else "⏸️ 已暂停")
        col4.metric("当前时间", get_beijing_time().strftime("%H:%M:%S"))

        # --------------- 心跳趋势：直线图 ---------------
        fig_seq = go.Figure()
        fig_seq.add_trace(go.Scatter(
            x=df['time'], y=df['seq'],
            mode='lines',  # 纯直线，不要点
            name='心跳序列',
            line=dict(color='#007bff', width=3)
        ))
        fig_seq.update_layout(
            title='心跳趋势（直线）',
            xaxis_title='时间（北京）',
            yaxis_title='序号',
            height=320
        )
        st.plotly_chart(fig_seq, use_container_width=True)

        # --------------- 心跳间隔 ---------------
        if len(hb_list) >= 2:
            intervals = [hb_list[i]['timestamp'] - hb_list[i-1]['timestamp'] for i in range(1, len(hb_list))]
            seqs = [x['seq'] for x in hb_list[1:]]
            fig_int = go.Figure()
            fig_int.add_trace(go.Scatter(
                x=seqs, y=intervals,
                mode='lines',
                name='间隔',
                line=dict(color='orange', width=2)
            ))
            fig_int.add_hline(y=1.0, line_dash='dash', line_color='green', annotation_text='标准1秒')
            fig_int.update_layout(title='心跳间隔（秒）', xaxis_title='序号', yaxis_title='秒', height=260)
            st.plotly_chart(fig_int, use_container_width=True)

        st.subheader("最近心跳（北京时间）")
        st.dataframe(df[['time_ms', 'seq']].tail(15), use_container_width=True)

    else:
        st.info("按 ▶️ 开始心跳，将每秒自动发送一条数据（中国时间）")

# ==================== 航线规划 ====================
else:
    st.header("🗺️ 航线规划")
    if st.session_state.waypoints:
        clng, clat = st.session_state.home_point
    else:
        clng, clat = OFFICIAL_LNG, OFFICIAL_LAT

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
        st.session_state.draw_points.append((lng, lat))
        save_state()

# ==================== 轻量自动刷新（不卡死） ====================
if "飞行监控" in st.session_state.page:
    time.sleep(0.8)
    st.rerun()

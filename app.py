import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
import threading
from datetime import datetime, timezone, timedelta
import folium
from streamlit_folium import st_folium
from folium import plugins

# ==================== 页面配置 ====================
st.set_page_config(page_title="南京科技职业学院 - 无人机地面站", layout="wide")

# ==================== 北京时间 ====================
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ)

def get_beijing_time_ms():
    return get_beijing_time().strftime("%H:%M:%S.%f")[:-3]

# ==================== 心跳线程（原版完全不动） ====================
class HeartbeatManager:
    def __init__(self):
        self.heartbeats = []
        self.sequence = 0
        self.last_time = get_beijing_time()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
    
    def _heartbeat_loop(self):
        while self.running:
            start = time.time()
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
                self.last_time = now
            elapsed = time.time() - start
            time.sleep(max(0, 1.0 - elapsed))
    
    def get_data(self):
        with self.lock:
            return self.heartbeats.copy(), self.sequence, self.last_time
    
    def get_connection_status(self):
        with self.lock:
            if not self.heartbeats:
                return "等待", 0
            last = self.heartbeats[-1]
            now = get_beijing_time()
            time_since = (now - datetime.fromtimestamp(last['timestamp'], BEIJING_TZ)).total_seconds()
            return ("在线", time_since) if time_since < 3 else ("超时", time_since)

# ==================== 坐标转换 ====================
class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003

# ==================== 地图 ====================
def create_map(center_lng, center_lat, waypoints, home, obstacles, coord):
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=18,
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德卫星'
    )
    folium.TileLayer(
        'https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8',
        name='高德街道'
    ).add_to(m)
    folium.TileLayer('OpenStreetMap').add_to(m)

    # 原点
    if home:
        lng, lat = home
        if coord == 'wgs84':
            lng, lat = CoordTransform.wgs84_to_gcj02(lng, lat)
        folium.Marker([lat, lng], icon=folium.Icon(color='green', icon='home'),
                      popup="南京科技职业学院").add_to(m)
        folium.Circle(radius=100, location=[lat, lng], color='green', fill=True, fill_opacity=0.15).add_to(m)

    # 航线
    if waypoints:
        pts = []
        for i, (lng, lat) in enumerate(waypoints):
            if coord == 'wgs84':
                lng, lat = CoordTransform.wgs84_to_gcj02(lng, lat)
            pts.append([lat, lng])
            folium.DivIcon(
                html=f'<div style="background:#000;color:white;width:22px;height:22px;border-radius:50%;text-align:center;line-height:22px;">{i+1}</div>'
            )
        folium.PolyLine(pts, color='blue', weight=3).add_to(m)

    # 障碍物（带高度）
    for ob in obstacles:
        ps = []
        for lng, lat in ob['points']:
            if coord == 'wgs84':
                lng, lat = CoordTransform.wgs84_to_gcj02(lng, lat)
            ps.append([lat, lng])
        folium.Polygon(
            locations=ps, color='red', fill=True, fill_opacity=0.4,
            popup=f"{ob['name']} | 高{ob['height']}m"
        ).add_to(m)

    # ========== 圈选工具（一定出现） ==========
    draw = plugins.Draw(
        draw_options={
            'polygon': True,
            'polyline': False, 'rectangle': False, 'circle': False, 'marker': False, 'circlemarker': False
        },
        edit_options={'edit': True, 'remove': True}
    )
    draw.add_to(m)
    folium.LayerControl().add_to(m)
    return m

# ==================== 初始化 ====================
if 'hb' not in st.session_state:
    st.session_state.hb = HeartbeatManager()
    st.session_state.hb.start()

if 'page' not in st.session_state:
    st.session_state.page = "监控"

if 'home' not in st.session_state:
    st.session_state.home = (118.749413, 32.234097)

if 'waypoints' not in st.session_state:
    st.session_state.waypoints = []

if 'a' not in st.session_state:
    st.session_state.a = (118.749413, 32.234097)
if 'b' not in st.session_state:
    st.session_state.b = (118.750500, 32.235200)

if 'coord' not in st.session_state:
    st.session_state.coord = 'wgs84'

# 障碍物（带高度）
if 'obstacles' not in st.session_state:
    st.session_state.obstacles = []
if 'obs_id' not in st.session_state:
    st.session_state.obs_id = 0

# 圈选临时数据
if 'draw_pending' not in st.session_state:
    st.session_state.draw_pending = None
if 'draw_hash' not in st.session_state:
    st.session_state.draw_hash = ""

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🎮 无人机地面站")
    st.markdown("**南京科技职业学院**")
    page = st.radio("功能", ["📡 飞行监控", "🗺️ 航线规划"])
    st.session_state.page = page

    # 心跳状态
    stat, ts = st.session_state.hb.get_connection_status()
    _, seq, _ = st.session_state.hb.get_data()
    if stat == "在线":
        st.success(f"✅ 在线 ({ts:.1f}s)")
    else:
        st.error(f"❌ 超时 ({ts:.1f}s)")
    st.metric("序列号", seq)

    if "航线规划" in page:
        st.session_state.coord = st.selectbox("坐标系", ["wgs84", "gcj02"],
                                              format_func=lambda x: "WGS84" if x == "wgs84" else "GCJ02")
        # 中心点
        st.subheader("中心点")
        hlng = st.number_input("经度", value=st.session_state.home[0], format="%.6f")
        hlat = st.number_input("纬度", value=st.session_state.home[1], format="%.6f")
        if st.button("更新中心点"):
            st.session_state.home = (hlng, hlat)
            st.rerun()

        # 航线
        st.subheader("航线 A→B")
        alng = st.number_input("A经度", value=st.session_state.a[0], format="%.6f")
        alat = st.number_input("A纬度", value=st.session_state.a[1], format="%.6f")
        blng = st.number_input("B经度", value=st.session_state.b[0], format="%.6f")
        blat = st.number_input("B纬度", value=st.session_state.b[1], format="%.6f")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("生成航线"):
                st.session_state.a = (alng, alat)
                st.session_state.b = (blng, blat)
                st.session_state.waypoints = [st.session_state.a, st.session_state.b]
        with c2:
            if st.button("清空航线"):
                st.session_state.waypoints = []

        # ========== 圈选后高度设置 ==========
        st.subheader("🚧 障碍物")
        if st.session_state.draw_pending is not None:
            st.warning("设置高度保存")
            h = st.number_input("高度(m)", 1, 500, 20)
            name = st.text_input("名称", f"障碍物{st.session_state.obs_id+1}")
            if st.button("✅ 保存"):
                st.session_state.obstacles.append({
                    "id": st.session_state.obs_id,
                    "name": name,
                    "height": h,
                    "points": st.session_state.draw_pending,
                    "time": get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
                })
                st.session_state.obs_id += 1
                st.session_state.draw_pending = None
                st.rerun()
            if st.button("❌ 取消"):
                st.session_state.draw_pending = None
                st.rerun()

        # 删除
        st.markdown("---")
        if st.session_state.obstacles:
            opt = [f"{i+1}. {o['name']}({o['height']}m)" for i, o in enumerate(st.session_state.obstacles)]
            sel = st.selectbox("删除障碍物", opt)
            if st.button("删除选中"):
                idx = int(sel.split(".")[0]) - 1
                st.session_state.obstacles.pop(idx)
                st.rerun()
        if st.button("清空所有"):
            st.session_state.obstacles = []
            st.session_state.obs_id = 0
            st.rerun()

# ==================== 飞行监控 ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控")
    hb_list, seq, _ = st.session_state.hb.get_data()
    if hb_list:
        df = pd.DataFrame(hb_list)
        st.dataframe(df[['time_ms', 'seq']].tail(15), use_container_width=True)
    else:
        st.info("等待心跳...")

# ==================== 航线规划（圈选地图） ====================
else:
    st.header("🗺️ 航线规划")
    st.success("✅ 右上角多边形工具可圈选障碍物")

    # 地图中心
    if st.session_state.waypoints:
        allp = [st.session_state.home] + st.session_state.waypoints
        clng = sum(p[0] for p in allp) / len(allp)
        clat = sum(p[1] for p in allp) / len(allp)
    else:
        clng, clat = st.session_state.home

    m = create_map(clng, clat,
                   st.session_state.waypoints,
                   st.session_state.home,
                   st.session_state.obstacles,
                   st.session_state.coord)

    # ========== 核心：安全获取圈选数据 ==========
    out = st_folium(m, width=1000, height=600, key="map")

    if out and out.get("last_draw") and st.session_state.draw_pending is None:
        d = out["last_draw"]
        if d.get("geometry", {}).get("type") == "Polygon":
            coords = d["geometry"]["coordinates"][0]
            pts = [(round(x, 6), round(y, 6)) for x, y in coords]
            st.session_state.draw_pending = pts
            st.rerun()

    # 显示障碍物
    if st.session_state.obstacles:
        st.subheader("障碍物列表")
        for o in st.session_state.obstacles:
            with st.expander(f"{o['name']} 高{o['height']}m"):
                st.write(f"时间：{o['time']}")
                for i, p in enumerate(o['points']):
                    st.write(f"{i+1}. {p[0]:.6f}, {p[1]:.6f}")

    # 距离
    if len(st.session_state.waypoints) >= 2:
        a, b = st.session_state.waypoints[0], st.session_state.waypoints[-1]
        dx = (b[0]-a[0])*111000*math.cos(math.radians((a[1]+b[1])/2))
        dy = (b[1]-a[1])*111000
        st.metric("距离", f"{math.hypot(dx, dy):.1f} 米")

# ========== 关键修复：只在监控页刷新，航线规划不刷新 ==========
if "飞行监控" in st.session_state.page:
    time.sleep(0.5)
    st.rerun()

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math
import threading
from datetime import datetime, timezone, timedelta
import folium
from streamlit_folium import st_folium
from folium import plugins

st.set_page_config(page_title="南京科技职业学院 - 无人机地面站", layout="wide")

# ==================== 北京时间 ====================
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ)

def get_beijing_time_ms():
    return datetime.now(BEIJING_TZ).strftime("%H:%M:%S.%f")[:-3]

# ==================== 心跳线程 ====================
class HeartbeatManager:
    def __init__(self):
        self.heartbeats = []
        self.sequence = 0
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            import time
            time.sleep(1)
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

    def get(self):
        with self.lock:
            return self.heartbeats.copy(), self.sequence

    def status(self):
        with self.lock:
            if not self.heartbeats:
                return "等待", 999
            last_ts = self.heartbeats[-1]['timestamp']
            now_ts = get_beijing_time().timestamp()
            delta = now_ts - last_ts
            if delta < 3:
                return "在线", delta
            else:
                return "超时", delta

# ==================== 坐标 ====================
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
        name='高德街道', attr='高德'
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='OSM').add_to(m)

    # HOME
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

    # 障碍物
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

    # 绘制工具
    draw = plugins.Draw(
        draw_options={
            'polygon': True, 'polyline': False, 'rectangle': False,
            'circle': False, 'marker': False, 'circlemarker': False
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

# 暂存绘制的多边形
if 'draw_geom' not in st.session_state:
    st.session_state.draw_geom = None

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🎮 无人机地面站")
    st.markdown("**南京科技职业学院**")
    page = st.radio("功能", ["📡 飞行监控", "🗺️ 航线规划"])
    st.session_state.page = page

    st.markdown("---")
    stat, ts = st.session_state.hb.status()
    _, seq = st.session_state.hb.get()
    if stat == "在线":
        st.success(f"✅ 在线 ({ts:.1f}s)")
    else:
        st.error(f"❌ 超时 ({ts:.1f}s)")
    st.metric("心跳序号", seq)

    if "航线规划" in page:
        st.markdown("---")
        st.session_state.coord = st.selectbox("坐标系", ["wgs84", "gcj02"],
                                              format_func=lambda x: "WGS84" if x == "wgs84" else "GCJ02")
        st.subheader("🏠 中心点")
        hlng = st.number_input("经度", value=st.session_state.home[0], format="%.6f")
        hlat = st.number_input("纬度", value=st.session_state.home[1], format="%.6f")
        if st.button("更新中心点"):
            st.session_state.home = (hlng, hlat)
            st.rerun()

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

        st.markdown("---")
        st.subheader("🚧 障碍物")
        st.info(f"总数：{len(st.session_state.obstacles)}")

        # 绘制后设置高度
        if st.session_state.draw_geom is not None:
            st.warning("设置高度保存障碍物")
            h = st.number_input("高度(m)", 1, 500, 20)
            nm = st.text_input("名称", f"障碍物{st.session_state.obs_id+1}")
            if st.button("✅ 保存障碍物"):
                st.session_state.obstacles.append({
                    "id": st.session_state.obs_id,
                    "name": nm,
                    "height": h,
                    "points": st.session_state.draw_geom,
                    "time": get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
                })
                st.session_state.obs_id += 1
                st.session_state.draw_geom = None
                st.success("保存成功")
                st.rerun()
            if st.button("❌ 取消"):
                st.session_state.draw_geom = None
                st.rerun()

        # 删除
        st.markdown("---")
        st.subheader("删除")
        if st.session_state.obstacles:
            opt = [f"{i+1}. {o['name']}({o['height']}m)" for i,o in enumerate(st.session_state.obstacles)]
            sel = st.selectbox("选择删除", opt)
            idx = int(sel.split(".")[0])-1
            if st.button("删除选中"):
                st.session_state.obstacles.pop(idx)
                st.rerun()
        if st.button("清空所有障碍物"):
            st.session_state.obstacles = []
            st.session_state.obs_id = 0
            st.rerun()

# ==================== 监控页面 ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控")
    hb_list, seq = st.session_state.hb.get()
    if hb_list:
        df = pd.DataFrame(hb_list)
        st.dataframe(df[['time_ms','seq']].tail(15), use_container_width=True)
    else:
        st.info("等待心跳...")

# ==================== 航线规划 ====================
else:
    st.header("🗺️ 航线规划")
    st.info("右上角多边形绘制 → 左侧设置高度 → 保存障碍物")

    # 地图中心点
    if st.session_state.waypoints:
        allp = [st.session_state.home] + st.session_state.waypoints
        clng = sum(p[0] for p in allp)/len(allp)
        clat = sum(p[1] for p in allp)/len(allp)
    else:
        clng, clat = st.session_state.home

    m = create_map(clng, clat,
                   st.session_state.waypoints,
                   st.session_state.home,
                   st.session_state.obstacles,
                   st.session_state.coord)

    out = st_folium(m, width=1000, height=600, key="map")

    # 捕获绘制
    if out and out.get("last_draw") and st.session_state.draw_geom is None:
        d = out["last_draw"]
        if d.get("geometry", {}).get("type") == "Polygon":
            coords = d["geometry"]["coordinates"][0]
            pts = [(round(x,6), round(y,6)) for x,y in coords]
            st.session_state.draw_geom = pts
            st.rerun()

    # 障碍物列表
    if st.session_state.obstacles:
        st.markdown("---")
        st.subheader("障碍物列表")
        for o in st.session_state.obstacles:
            with st.expander(f"{o['name']} ｜ {o['height']}米"):
                st.write(f"时间：{o['time']}")
                st.write(f"点数：{len(o['points'])}")
                for i,p in enumerate(o['points']):
                    st.write(f"{i+1}. {p[0]:.6f}, {p[1]:.6f}")

    # 距离
    if len(st.session_state.waypoints)>=2:
        a = st.session_state.waypoints[0]
        b = st.session_state.waypoints[-1]
        dx = (b[0]-a[0])*111000*math.cos(math.radians((a[1]+b[1])/2))
        dy = (b[1]-a[1])*111000
        dis = math.hypot(dx, dy)
        st.metric("航线距离", f"{dis:.1f} 米")

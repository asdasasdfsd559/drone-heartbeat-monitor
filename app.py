import streamlit as st
import folium
from streamlit_folium import st_folium
from folium import plugins
import pandas as pd
import plotly.graph_objects as go
import time
import math
import threading
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="南京科技职业学院 - 无人机地面站", layout="wide")

# ==================== 北京时间 ====================
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ)

# ==================== 心跳线程 ====================
class HeartbeatManager:
    def __init__(self):
        self.heartbeats = []
        self.sequence = 0
        self.last_time = get_beijing_time()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()
    
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
            time.sleep(max(0, 1.0 - (time.time() - start)))
    
    def get_data(self):
        with self.lock:
            return self.heartbeats.copy(), self.sequence, self.last_time
    
    def get_connection_status(self):
        with self.lock:
            if not self.heartbeats:
                return "等待", 0
            last = self.heartbeats[-1]
            now = get_beijing_time()
            last_dt = datetime.fromtimestamp(last['timestamp'], tz=BEIJING_TZ)
            time_since = (now - last_dt).total_seconds()
            return ("在线", time_since) if time_since < 3 else ("超时", time_since)

# ==================== 坐标转换 ====================
class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003

# ==================== 创建地图（显示已有障碍物和临时多边形） ====================
def create_map(center_lng, center_lat, waypoints, home_point, obstacles, temp_polygon, coord_system):
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    m = folium.Map(location=[display_lat, display_lng], zoom_start=18, control_scale=True)
    folium.TileLayer('https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}', attr='高德地图', name='高德卫星图').add_to(m)
    folium.TileLayer('OpenStreetMap', name='OSM街道图').add_to(m)
    
    if home_point:
        folium.Marker([display_lat, display_lng], popup='🏠 学校中心点', icon=folium.Icon(color='green')).add_to(m)
        folium.Circle(radius=100, location=[display_lat, display_lng], color='green', fill=True, fill_opacity=0.15).add_to(m)
    
    if waypoints:
        points = []
        for i, wp in enumerate(waypoints):
            points.append([wp[1], wp[0]])
            color = 'blue' if i < len(waypoints)-1 else 'red'
            folium.Marker([wp[1], wp[0]], popup=f'航点 {i+1}', icon=folium.Icon(color=color)).add_to(m)
        folium.PolyLine(points, color='blue', weight=3).add_to(m)
    
    # 已保存的障碍物（红色）
    for obs in obstacles:
        pts = [[p[1], p[0]] for p in obs['points']]
        height = obs.get('height', 10)
        fill_color = '#ff9999' if height < 20 else ('#ff6666' if height < 50 else '#ff3333')
        folium.Polygon(locations=pts, color='red', weight=3, fill=True, fill_color=fill_color, fill_opacity=0.5,
                       popup=f"{obs['name']} ({height}米)").add_to(m)
    
    # 临时多边形（橙色预览）
    if temp_polygon and len(temp_polygon) >= 3:
        pts = [[p[1], p[0]] for p in temp_polygon]
        folium.Polygon(locations=pts, color='orange', weight=3, fill=True, fill_color='orange', fill_opacity=0.3,
                       popup="待保存障碍物").add_to(m)
    
    # 绘图工具
    draw = plugins.Draw(
        draw_options={
            'polygon': {'allowIntersection': False, 'shapeOptions': {'color': '#ff0000', 'fillColor': '#ff0000', 'fillOpacity': 0.3}, 'repeatMode': True},
            'polyline': False, 'rectangle': False, 'circle': False, 'marker': False, 'circlemarker': False
        },
        edit_options={'edit': True, 'remove': True}
    )
    draw.add_to(m)
    folium.LayerControl().add_to(m)
    return m

# ==================== 初始化 ====================
if 'heartbeat_mgr' not in st.session_state:
    st.session_state.heartbeat_mgr = HeartbeatManager()
    st.session_state.heartbeat_mgr.start()

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

SCHOOL_CENTER = (118.749413, 32.234097)
if 'home_point' not in st.session_state:
    st.session_state.home_point = SCHOOL_CENTER

if 'waypoints' not in st.session_state:
    st.session_state.waypoints = []

if 'a_point' not in st.session_state:
    st.session_state.a_point = SCHOOL_CENTER

if 'b_point' not in st.session_state:
    st.session_state.b_point = (SCHOOL_CENTER[0] + 0.001, SCHOOL_CENTER[1] + 0.001)

if 'coord_system' not in st.session_state:
    st.session_state.coord_system = 'wgs84'

if 'obstacles' not in st.session_state:
    st.session_state.obstacles = []  # 初始为空

if 'temp_polygon' not in st.session_state:
    st.session_state.temp_polygon = None

if 'next_id' not in st.session_state:
    st.session_state.next_id = 1

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🎮 无人机地面站")
    st.markdown("**南京科技职业学院**")
    
    selected_page = st.radio("选择功能", ["📡 飞行监控", "🗺️ 航线规划"], key="page_select")
    st.session_state.page = selected_page
    
    st.markdown("---")
    status, time_since = st.session_state.heartbeat_mgr.get_connection_status()
    _, seq, _ = st.session_state.heartbeat_mgr.get_data()
    if status == "在线":
        st.success(f"✅ 心跳正常 ({time_since:.1f}秒前)")
        st.metric("当前序列号", seq)
    else:
        st.error(f"❌ 超时！{time_since:.1f}秒无心跳")
    
    if "🗺️ 航线规划" in st.session_state.page:
        st.markdown("---")
        st.subheader("🏠 航线设置")
        a_lng = st.number_input("起点经度", value=st.session_state.a_point[0], format="%.6f", key="a_lng")
        a_lat = st.number_input("起点纬度", value=st.session_state.a_point[1], format="%.6f", key="a_lat")
        b_lng = st.number_input("终点经度", value=st.session_state.b_point[0], format="%.6f", key="b_lng")
        b_lat = st.number_input("终点纬度", value=st.session_state.b_point[1], format="%.6f", key="b_lat")
        if st.button("✈️ 生成/更新航线"):
            st.session_state.a_point = (a_lng, a_lat)
            st.session_state.b_point = (b_lng, b_lat)
            st.session_state.waypoints = [st.session_state.a_point, st.session_state.b_point]
            st.rerun()
        
        st.markdown("---")
        st.subheader("🚧 障碍物管理")
        st.info(f"当前障碍物数量: {len(st.session_state.obstacles)}")
        if st.session_state.obstacles:
            for i, obs in enumerate(st.session_state.obstacles):
                st.write(f"{i+1}. {obs['name']} (高度: {obs['height']}米)")
        
        # 如果存在临时多边形，显示保存表单
        if st.session_state.temp_polygon:
            st.warning("⚠️ 检测到新绘制的多边形，请填写信息后保存")
            new_name = st.text_input("障碍物名称", key="temp_name")
            new_height = st.number_input("高度(米)", min_value=1, value=20, step=5, key="temp_height")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 确认保存", key="save_btn"):
                    if new_name:
                        st.session_state.obstacles.append({
                            'id': st.session_state.next_id,
                            'name': new_name,
                            'height': new_height,
                            'points': st.session_state.temp_polygon,
                            'created_at': get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        st.session_state.next_id += 1
                        st.session_state.temp_polygon = None
                        st.success(f"已添加障碍物: {new_name}")
                        st.rerun()
                    else:
                        st.error("请输入名称")
            with col2:
                if st.button("🗑️ 放弃", key="discard_btn"):
                    st.session_state.temp_polygon = None
                    st.rerun()
        else:
            st.info("💡 使用地图右上角的多边形工具绘制区域，绘制后双击完成，然后在左侧填写名称和高度保存")
        
        st.markdown("---")
        if st.session_state.obstacles:
            if st.button("🗑️ 清空所有障碍物", key="clear_all"):
                st.session_state.obstacles = []
                st.rerun()

# ==================== 主内容 ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控 - 心跳数据")
    heartbeats, seq, _ = st.session_state.heartbeat_mgr.get_data()
    if heartbeats:
        df = pd.DataFrame(heartbeats)
        st.dataframe(df[['time_ms', 'seq']].tail(20))
    else:
        st.info("等待心跳数据...")
else:
    st.header("🗺️ 航线规划 - 多边形圈选障碍物")
    if st.session_state.waypoints:
        a, b = st.session_state.waypoints
        dx = (b[0] - a[0]) * 111000 * math.cos(math.radians((a[1] + b[1]) / 2))
        dy = (b[1] - a[1]) * 111000
        distance = math.sqrt(dx*dx + dy*dy)
        st.info(f"✈️ 当前航线距离: {distance:.1f} 米")
    else:
        st.warning("⚠️ 请先在左侧设置起点和终点")
    
    # 显示地图
    m = create_map(
        st.session_state.home_point[0], st.session_state.home_point[1],
        st.session_state.waypoints, st.session_state.home_point,
        st.session_state.obstacles, st.session_state.temp_polygon,
        st.session_state.coord_system
    )
    output = st_folium(m, width=1000, height=600, returned_objects=["last_draw"])
    
    # 检测新绘制的多边形
    if output and output.get('last_draw'):
        draw_data = output['last_draw']
        if draw_data and draw_data.get('geometry') and draw_data['geometry']['type'] == 'Polygon':
            coords = draw_data['geometry']['coordinates'][0]
            points = [(c[0], c[1]) for c in coords]
            if len(points) >= 3 and st.session_state.temp_polygon is None:
                st.session_state.temp_polygon = points
                st.rerun()

# 自动刷新心跳
time.sleep(0.5)
st.rerun()

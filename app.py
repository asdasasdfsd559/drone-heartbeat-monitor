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
import json

st.set_page_config(page_title="南京科技职业学院 - 无人机地面站", layout="wide")

# ==================== 北京时间工具函数 ====================
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ)

def get_beijing_time_ms():
    now = get_beijing_time()
    return now.strftime("%H:%M:%S.%f")[:-3]

# ==================== 独立心跳线程 ====================
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
            sleep_time = max(0, 1.0 - elapsed)
            time.sleep(sleep_time)
    
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
            if time_since < 3:
                return "在线", time_since
            else:
                return "超时", time_since

# ==================== 坐标系转换 ====================
class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003
    
    @staticmethod
    def gcj02_to_wgs84(lng, lat):
        return lng - 0.0005, lat - 0.0003

# ==================== 地图函数（带多边形绘制） ====================
def create_map_with_drawing(center_lng, center_lat, waypoints, home_point, obstacles, coord_system):
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=18,
        control_scale=True,
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德地图'
    )
    
    folium.TileLayer(
        'https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        name='高德街道图', attr='高德地图'
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='OSM街道图').add_to(m)
    
    # Home点
    if home_point:
        h_lng, h_lat = home_point if coord_system == 'gcj02' else CoordTransform.wgs84_to_gcj02(*home_point)
        folium.Marker([h_lat, h_lng], popup='🏠 南京科技职业学院', 
                      icon=folium.Icon(color='green', icon='home')).add_to(m)
        folium.Circle(radius=100, location=[h_lat, h_lng], color='green', fill=True, fill_opacity=0.15).add_to(m)
    
    # 航线
    if waypoints:
        points = []
        for i, wp in enumerate(waypoints):
            wp_lng, wp_lat = wp if coord_system == 'gcj02' else CoordTransform.wgs84_to_gcj02(*wp)
            points.append([wp_lat, wp_lng])
            color = 'blue' if i < len(waypoints)-1 else 'red'
            folium.Marker([wp_lat, wp_lng], popup=f'航点{i+1}', 
                          icon=folium.Icon(color=color, icon='circle')).add_to(m)
        folium.PolyLine(points, color='blue', weight=3).add_to(m)
    
    # 障碍物（带高度）
    for obs in obstacles:
        polygon_points = []
        for p in obs['points']:
            plng, plat = p if coord_system == 'gcj02' else CoordTransform.wgs84_to_gcj02(*p)
            polygon_points.append([plat, plng])
        folium.Polygon(
            locations=polygon_points, color='red', weight=3, fill=True, fill_opacity=0.4,
            popup=f"🚧 {obs['name']}\n高度：{obs['height']}米",
            tooltip=f"{obs['name']} | 高{obs['height']}m"
        ).add_to(m)
    
    # 绘制工具（只允许画多边形）
    draw = plugins.Draw(
        draw_options={
            'polygon': {'allowIntersection': False, 'shapeOptions': {'color': '#ff0000'}},
            'polyline': False, 'rectangle': False, 'circle': False, 'marker': False, 'circlemarker': False
        },
        edit_options={'edit': False, 'remove': False}
    )
    draw.add_to(m)
    
    # 距离圈
    for r in [50, 100, 200]:
        folium.Circle(radius=r, location=[display_lat, display_lng], color='gray', fill=False, weight=1).add_to(m)
    
    folium.LayerControl().add_to(m)
    return m

# ==================== 初始化 ====================
if 'heartbeat_mgr' not in st.session_state:
    st.session_state.heartbeat_mgr = HeartbeatManager()
    st.session_state.heartbeat_mgr.start()

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

if 'home_point' not in st.session_state:
    st.session_state.home_point = (118.749413, 32.234097)

if 'waypoints' not in st.session_state:
    st.session_state.waypoints = []

if 'a_point' not in st.session_state:
    st.session_state.a_point = (118.749413, 32.234097)

if 'b_point' not in st.session_state:
    st.session_state.b_point = (118.750500, 32.235200)

if 'coord_system' not in st.session_state:
    st.session_state.coord_system = 'wgs84'

# ========== 障碍物（带高度 + 临时绘制）==========
if 'obstacles' not in st.session_state:
    st.session_state.obstacles = [
        {'id': 0, 'name': '教学楼A区', 'height': 15,
         'points': [(118.749000, 32.233800),(118.749500, 32.233800),
                    (118.749500, 32.234200),(118.749000, 32.234200)],
         'created_at': get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")}
    ]

if 'next_obstacle_id' not in st.session_state:
    st.session_state.next_obstacle_id = 1

# 临时存储绘制的多边形（未确认保存）
if 'temp_polygon' not in st.session_state:
    st.session_state.temp_polygon = None

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🎮 无人机地面站")
    st.markdown("**南京科技职业学院**")
    
    selected_page = st.radio(
        "选择功能", ["📡 飞行监控", "🗺️ 航线规划"],
        index=0 if st.session_state.page == "飞行监控" else 1
    )
    st.session_state.page = selected_page
    
    status, time_since = st.session_state.heartbeat_mgr.get_connection_status()
    _, seq, _ = st.session_state.heartbeat_mgr.get_data()
    
    if status == "在线":
        st.success(f"✅ 心跳正常 ({time_since:.1f}s前)")
        st.metric("序列号", seq)
    else:
        st.error(f"❌ 超时 {time_since:.1f}s")
    
    if "🗺️ 航线规划" in st.session_state.page:
        st.markdown("---")
        st.session_state.coord_system = st.selectbox(
            "坐标系", ['wgs84','gcj02'], format_func=lambda x: "WGS-84(GPS)" if x=="wgs84" else "GCJ-02(高德)"
        )
        
        st.subheader("🏠 中心点")
        home_lng = st.number_input("经度", value=st.session_state.home_point[0], format="%.6f")
        home_lat = st.number_input("纬度", value=st.session_state.home_point[1], format="%.6f")
        if st.button("更新中心点"):
            st.session_state.home_point = (home_lng, home_lat)
            st.rerun()
        
        st.subheader("📍 起点A / 终点B")
        a_lng = st.number_input("A经度", value=st.session_state.a_point[0], format="%.6f", key="al")
        a_lat = st.number_input("A纬度", value=st.session_state.a_point[1], format="%.6f", key="alat")
        b_lng = st.number_input("B经度", value=st.session_state.b_point[0], format="%.6f", key="bl")
        b_lat = st.number_input("B纬度", value=st.session_state.b_point[1], format="%.6f", key="blat")
        
        c1,c2 = st.columns(2)
        with c1:
            if st.button("➕ 生成航线"):
                st.session_state.a_point = (a_lng,a_lat)
                st.session_state.b_point = (b_lng,b_lat)
                st.session_state.waypoints = [(a_lng,a_lat),(b_lng,b_lat)]
                st.success("已生成航线")
                st.rerun()
        with c2:
            if st.button("🗑️ 清空航线"):
                st.session_state.waypoints = []
                st.rerun()
        
        st.markdown("---")
        st.subheader("🚧 障碍物")
        st.info(f"总数：{len(st.session_state.obstacles)}")
        
        # 删除障碍物
        if st.session_state.obstacles:
            del_opt = st.selectbox("删除障碍物", 
                [f"{o['name']} (高{o['height']}m)" for o in st.session_state.obstacles])
            if st.button("删除选中"):
                idx = [f"{o['name']} (高{o['height']}m)" for o in st.session_state.obstacles].index(del_opt)
                st.session_state.obstacles.pop(idx)
                st.success("已删除")
                st.rerun()
        
        if st.button("清空所有障碍物"):
            st.session_state.obstacles = []
            st.session_state.next_obstacle_id = 0
            st.success("已清空")
            st.rerun()

# ==================== 主页面 ====================
if "📡 飞行监控" in st.session_state.page:
    st.header("📡 飞行监控")
    heartbeats, seq, _ = st.session_state.heartbeat_mgr.get_data()
    if heartbeats:
        df = pd.DataFrame(heartbeats)
        col1,col2,col3,col4 = st.columns(4)
        col1.metric("总心跳", len(df))
        col2.metric("当前序列号", seq)
        status, _ = st.session_state.heartbeat_mgr.get_connection_status()
        col3.metric("连接状态", "✅ 在线" if status=="在线" else "❌ 离线")
        col4.metric("丢包率", f"{max(0, seq-len(df))/seq*100:.1f}%" if seq>0 else "0%")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['time'], y=df['seq'], mode='lines+markers', line=dict(color='blue')))
        fig.update_layout(title="心跳趋势", height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(df[['time_ms','seq']].tail(15), use_container_width=True)

else:
    st.header("🗺️ 航线规划 - 障碍物圈选（已修复）")
    st.warning("""
    ✅ **使用教程**
    1. 点击地图右上角多边形图标
    2. 在地图上圈选障碍物区域 → 双击完成
    3. 输入障碍物高度 → 点击确认保存
    4. 保存后会永久显示在地图上
    """)

    # 地图渲染
    try:
        center = st.session_state.home_point
        if st.session_state.waypoints:
            allp = [st.session_state.home_point] + st.session_state.waypoints
            center = (sum(p[0] for p in allp)/len(allp), sum(p[1] for p in allp)/len(allp))
        
        m = create_map_with_drawing(
            center[0], center[1],
            st.session_state.waypoints,
            st.session_state.home_point,
            st.session_state.obstacles,
            st.session_state.coord_system
        )
        output = st_folium(m, width=1000, height=600, key="map", returned_objects=["last_draw"])

        # ========== 核心修复：圈选后不自动保存，等待输入高度 ==========
        if output and output.get("last_draw"):
            geo = output["last_draw"]["geometry"]
            if geo and geo["type"] == "Polygon":
                coords = geo["coordinates"][0]
                points = [(round(c[0],6), round(c[1],6)) for c in coords]
                st.session_state.temp_polygon = points

        # 有临时绘制 → 显示高度输入框
        if st.session_state.temp_polygon:
            st.markdown("---")
            st.subheader("✅ 圈选完成，请设置障碍物高度")
            height = st.number_input("障碍物高度（米）", min_value=1, value=20, step=1)
            name = st.text_input("障碍物名称", value=f"障碍物{st.session_state.next_obstacle_id+1}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 确认保存障碍物"):
                    new_obs = {
                        "id": st.session_state.next_obstacle_id,
                        "name": name,
                        "height": height,
                        "points": st.session_state.temp_polygon,
                        "created_at": get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    st.session_state.obstacles.append(new_obs)
                    st.session_state.next_obstacle_id += 1
                    st.session_state.temp_polygon = None
                    st.success(f"已保存：{name}（{height}米）")
                    st.rerun()
            with col2:
                if st.button("❌ 取消绘制"):
                    st.session_state.temp_polygon = None
                    st.warning("已取消当前绘制")
                    st.rerun()

        # 显示障碍物列表
        if st.session_state.obstacles:
            st.markdown("---")
            st.subheader("🚧 已保存障碍物")
            for idx, obs in enumerate(st.session_state.obstacles):
                with st.expander(f"{idx+1}. {obs['name']} | 高{obs['height']}m"):
                    st.write(f"创建时间：{obs['created_at']}")
                    st.write(f"顶点数：{len(obs['points'])}")
                    st.write(f"坐标：{obs['points']}")

    except Exception as e:
        st.error(f"地图异常：{e}")

# 防止疯狂刷新（只在监控页自动刷新）
if "📡 飞行监控" in st.session_state.page:
    time.sleep(0.5)
    st.rerun()

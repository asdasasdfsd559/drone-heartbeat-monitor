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
            last_dt = datetime.fromtimestamp(last['timestamp'], tz=BEIJING_TZ)
            time_since = (now - last_dt).total_seconds()
            return ("在线", time_since) if time_since < 3 else ("超时", time_since)

# ==================== 坐标转换 ====================

def wgs84_to_gcj02(lng, lat):
    return lng + 0.0005, lat + 0.0003

# ==================== 地图函数 ====================

def create_simple_map(center_lng, center_lat, obstacles):
    """创建简单的地图"""
    
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=17,
        control_scale=True
    )
    
    # 学校中心点
    folium.Marker(
        [center_lat, center_lng], 
        popup='🏠 南京科技职业学院', 
        icon=folium.Icon(color='green')
    ).add_to(m)
    
    # 障碍物
    for obs in obstacles:
        points = [[p[1], p[0]] for p in obs['points']]  # 转换为 [lat, lng]
        folium.Polygon(
            locations=points,
            color='red',
            weight=3,
            fill=True,
            fill_opacity=0.4,
            popup=f"{obs['name']} (高度:{obs['height']}米)"
        ).add_to(m)
    
    # 绘制工具
    draw = plugins.Draw(
        draw_options={
            'polygon': {'repeatMode': True},
            'polyline': False,
            'rectangle': False,
            'circle': False,
            'marker': False,
            'circlemarker': False
        }
    )
    draw.add_to(m)
    
    return m

# ==================== 初始化 ====================

if 'heartbeat_mgr' not in st.session_state:
    st.session_state.heartbeat_mgr = HeartbeatManager()
    st.session_state.heartbeat_mgr.start()

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

# 学校坐标
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

# 障碍物
if 'obstacles' not in st.session_state:
    st.session_state.obstacles = []

if 'temp_polygon' not in st.session_state:
    st.session_state.temp_polygon = None

# ==================== 侧边栏 ====================

with st.sidebar:
    st.title("🎮 无人机地面站")
    st.markdown("**南京科技职业学院**")
    
    selected_page = st.radio(
        "选择功能",
        ["📡 飞行监控", "🗺️ 航线规划"],
        index=0 if st.session_state.page == "飞行监控" else 1,
        key="page_select"
    )
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
        
        # 坐标系选择
        coord = st.selectbox("坐标系", ['wgs84', 'gcj02'])
        st.session_state.coord_system = coord
        
        st.markdown("---")
        st.subheader("📍 起点/终点")
        
        a_lng = st.number_input("起点经度", value=st.session_state.a_point[0], format="%.6f")
        a_lat = st.number_input("起点纬度", value=st.session_state.a_point[1], format="%.6f")
        b_lng = st.number_input("终点经度", value=st.session_state.b_point[0], format="%.6f")
        b_lat = st.number_input("终点纬度", value=st.session_state.b_point[1], format="%.6f")
        
        if st.button("生成航线"):
            st.session_state.a_point = (a_lng, a_lat)
            st.session_state.b_point = (b_lng, b_lat)
            st.session_state.waypoints = [(a_lng, a_lat), (b_lng, b_lat)]
            st.success("航线已生成")
            st.rerun()
        
        st.markdown("---")
        st.subheader("🚧 障碍物管理")
        
        st.info(f"障碍物数量: {len(st.session_state.obstacles)}")
        
        # 显示临时多边形状态
        if st.session_state.temp_polygon:
            st.success(f"已绘制多边形 ({len(st.session_state.temp_polygon)}个顶点)")
        
        # 添加障碍物
        new_name = st.text_input("障碍物名称", placeholder="教学楼", key="new_name")
        new_height = st.number_input("高度(米)", min_value=1, value=20, key="new_height")
        
        if st.button("保存障碍物", use_container_width=True):
            if st.session_state.temp_polygon and len(st.session_state.temp_polygon) >= 3:
                if new_name:
                    st.session_state.obstacles.append({
                        'id': len(st.session_state.obstacles) + 1,
                        'name': new_name,
                        'height': new_height,
                        'points': st.session_state.temp_polygon
                    })
                    st.session_state.temp_polygon = None
                    st.success(f"已添加: {new_name}")
                    st.rerun()
                else:
                    st.error("请输入名称")
            else:
                st.error("请先在地图上绘制多边形")
        
        # 删除障碍物
        if st.session_state.obstacles:
            st.markdown("---")
            del_options = [f"{o['id']}. {o['name']}" for o in st.session_state.obstacles]
            del_sel = st.selectbox("删除障碍物", del_options)
            if st.button("删除"):
                del_id = int(del_sel.split('.')[0])
                st.session_state.obstacles = [o for o in st.session_state.obstacles if o['id'] != del_id]
                st.rerun()

# ==================== 主内容 ====================

if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控")
    
    heartbeats, seq, _ = st.session_state.heartbeat_mgr.get_data()
    
    if heartbeats:
        df = pd.DataFrame(heartbeats)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("总心跳数", len(df))
        col2.metric("当前序列号", seq)
        
        status, ts = st.session_state.heartbeat_mgr.get_connection_status()
        col3.metric("连接状态", "✅ 在线" if status == "在线" else "❌ 离线")
        
        if status == "超时":
            st.error(f"⚠️ 超时！{ts:.1f}秒无心跳")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['time'], y=df['seq'], mode='lines+markers', name='心跳'))
        fig.update_layout(title="心跳序列号", height=300)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(df[['time_ms', 'seq']].tail(20), use_container_width=True)
    else:
        st.info("等待心跳...")

else:
    st.header("🗺️ 航线规划")
    
    col1, col2 = st.columns(2)
    col1.info(f"学校: 南京科技职业学院")
    col2.info(f"障碍物: {len(st.session_state.obstacles)}个")
    
    st.markdown("---")
    
    with st.spinner("加载地图..."):
        try:
            # 计算中心点
            if st.session_state.waypoints:
                all_points = [st.session_state.home_point] + st.session_state.waypoints
                center_lng = sum(p[0] for p in all_points) / len(all_points)
                center_lat = sum(p[1] for p in all_points) / len(all_points)
            else:
                center_lng, center_lat = st.session_state.home_point
            
            # 创建地图
            m = create_simple_map(center_lng, center_lat, st.session_state.obstacles)
            
            # 添加航点线
            if st.session_state.waypoints:
                points = [[p[1], p[0]] for p in st.session_state.waypoints]
                folium.PolyLine(points, color='blue', weight=3).add_to(m)
                for i, wp in enumerate(st.session_state.waypoints):
                    folium.Marker([wp[1], wp[0]], popup=f'航点{i+1}').add_to(m)
            
            output = st_folium(m, width=1000, height=600, returned_objects=["last_draw"])
            
            # 处理绘制的多边形
            if output and output.get('last_draw'):
                draw_data = output['last_draw']
                if draw_data and draw_data.get('geometry'):
                    coords = draw_data['geometry']['coordinates'][0]
                    points = [(c[0], c[1]) for c in coords]
                    if len(points) >= 3:
                        st.session_state.temp_polygon = points
                        st.success(f"已绘制多边形，共{len(points)}个顶点")
                        st.rerun()
            
            st.success("地图加载成功")
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
            st.info("请刷新页面重试")

time.sleep(0.5)
st.rerun()

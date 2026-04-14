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

# ==================== 创建地图（带绘图工具） ====================
def create_map(center_lng, center_lat, obstacles):
    m = folium.Map(location=[center_lat, center_lng], zoom_start=18, control_scale=True)
    # 底图：高德卫星图（国内访问较快，无需注册也可用）
    folium.TileLayer(
        'https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德地图',
        name='高德卫星图'
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='OSM街道图').add_to(m)
    
    # 绘制已保存的障碍物
    for obs in obstacles:
        points = [[p[1], p[0]] for p in obs['points']]
        folium.Polygon(
            locations=points,
            color='red',
            weight=3,
            fill=True,
            fill_opacity=0.5,
            popup=f"{obs['name']} ({obs['height']}米)"
        ).add_to(m)
    
    # 添加绘图控件
    draw = plugins.Draw(
        draw_options={
            'polygon': True,
            'polyline': False,
            'rectangle': False,
            'circle': False,
            'marker': False,
            'circlemarker': False
        },
        edit_options={'edit': True, 'remove': True}
    )
    draw.add_to(m)
    folium.LayerControl().add_to(m)
    return m

# ==================== 初始化 session_state ====================
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

if 'obstacles' not in st.session_state:
    st.session_state.obstacles = []   # 初始为空

# 暂存新绘制的多边形顶点
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
        st.subheader("🏠 航线设置")
        col1, col2 = st.columns(2)
        with col1:
            a_lng = st.number_input("起点经度", value=st.session_state.a_point[0], format="%.6f", key="a_lng")
            a_lat = st.number_input("起点纬度", value=st.session_state.a_point[1], format="%.6f", key="a_lat")
        with col2:
            b_lng = st.number_input("终点经度", value=st.session_state.b_point[0], format="%.6f", key="b_lng")
            b_lat = st.number_input("终点纬度", value=st.session_state.b_point[1], format="%.6f", key="b_lat")
        
        if st.button("✈️ 生成/更新航线", key="gen_route"):
            st.session_state.a_point = (a_lng, a_lat)
            st.session_state.b_point = (b_lng, b_lat)
            st.session_state.waypoints = [st.session_state.a_point, st.session_state.b_point]
            st.success("航线已更新")
            st.rerun()
        
        st.markdown("---")
        st.subheader("🚧 障碍物管理")
        st.info(f"当前障碍物数量: {len(st.session_state.obstacles)}")
        if st.session_state.obstacles:
            for i, obs in enumerate(st.session_state.obstacles):
                st.write(f"{i+1}. {obs['name']} (高度: {obs['height']}米)")
        if st.button("🗑️ 清空所有障碍物", key="clear_all"):
            st.session_state.obstacles = []
            st.rerun()
        
        # 如果存在临时多边形，显示保存表单
        if st.session_state.temp_polygon:
            st.markdown("---")
            st.warning("检测到新绘制的多边形，请填写信息后保存")
            new_name = st.text_input("障碍物名称", key="temp_name")
            new_height = st.number_input("高度(米)", min_value=1, value=20, step=5, key="temp_height")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 保存", key="save_polygon"):
                    if new_name:
                        st.session_state.obstacles.append({
                            'name': new_name,
                            'height': new_height,
                            'points': st.session_state.temp_polygon,
                            'created_at': get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        st.session_state.temp_polygon = None
                        st.success(f"已添加障碍物: {new_name}")
                        st.rerun()
                    else:
                        st.error("请输入名称")
            with col2:
                if st.button("🗑️ 放弃", key="discard_polygon"):
                    st.session_state.temp_polygon = None
                    st.rerun()

# ==================== 主内容 ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控 - 心跳数据")
    st.caption("🕐 北京时间 (UTC+8)")
    heartbeats, seq, _ = st.session_state.heartbeat_mgr.get_data()
    if heartbeats:
        df = pd.DataFrame(heartbeats)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总心跳数", len(df))
        col2.metric("当前序列号", seq)
        if len(heartbeats) >= 2:
            intervals = [heartbeats[i]['timestamp'] - heartbeats[i-1]['timestamp'] for i in range(1, len(heartbeats))]
            avg_interval = sum(intervals) / len(intervals)
            st.metric("平均间隔", f"{avg_interval:.3f}秒")
        status, time_since = st.session_state.heartbeat_mgr.get_connection_status()
        col3.metric("连接状态", "✅ 在线" if status == "在线" else "❌ 离线")
        expected = seq
        received = len(df)
        loss_rate = (expected - received) / expected * 100 if expected > 0 else 0
        col4.metric("丢包率", f"{loss_rate:.1f}%")
        if status == "超时":
            st.error(f"⚠️ 连接超时！已 {time_since:.1f} 秒未收到心跳")
        if len(heartbeats) >= 2:
            fig_interval = go.Figure()
            intervals_data = [heartbeats[i]['timestamp'] - heartbeats[i-1]['timestamp'] for i in range(1, len(heartbeats))]
            seqs = [heartbeats[i]['seq'] for i in range(1, len(heartbeats))]
            fig_interval.add_trace(go.Scatter(x=seqs, y=intervals_data, mode='lines+markers', name='心跳间隔', line=dict(color='orange', width=2)))
            fig_interval.add_hline(y=1.0, line_dash="dash", line_color="green", annotation_text="目标间隔1秒")
            fig_interval.update_layout(title="心跳间隔精确度分析", xaxis_title="序列号", yaxis_title="间隔 (秒)", height=300)
            st.plotly_chart(fig_interval, use_container_width=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['time'], y=df['seq'], mode='lines+markers', name='心跳', line=dict(color='blue', width=2)))
        fig.update_layout(title="心跳序列号趋势", xaxis_title="北京时间", yaxis_title="序列号", height=300)
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("📋 详细心跳数据")
        display_df = df[['time_ms', 'seq']].tail(20).copy()
        display_df.columns = ['北京时间 (精确到毫秒)', '序列号']
        st.dataframe(display_df, use_container_width=True)
        latest = heartbeats[-1]
        st.success(f"✅ 最新心跳: {latest['time_ms']} | 序列号: {latest['seq']}")
        st.caption(f"🕐 当前北京时间: {get_beijing_time().strftime('%Y年%m月%d日 %H:%M:%S')}")
    else:
        st.info("等待心跳数据...")

else:
    st.header("🗺️ 航线规划 - 多边形圈选障碍物")
    st.caption("1. 点击地图右上角多边形工具绘制区域，双击完成\n2. 绘制后左侧会出现保存表单，输入名称和高度后保存")
    
    if st.session_state.waypoints:
        a, b = st.session_state.waypoints
        dx = (b[0] - a[0]) * 111000 * math.cos(math.radians((a[1] + b[1]) / 2))
        dy = (b[1] - a[1]) * 111000
        distance = math.sqrt(dx*dx + dy*dy)
        st.info(f"✈️ 当前航线：起点 → 终点，直线距离约 {distance:.1f} 米")
    else:
        st.warning("⚠️ 暂无航线，请在左侧设置起点和终点并点击「生成/更新航线」")
    
    # 显示地图
    m = create_map(st.session_state.home_point[0], st.session_state.home_point[1], st.session_state.obstacles)
    output = st_folium(m, width=1000, height=600, returned_objects=["last_draw"])
    
    # 检测新绘制的多边形（不自动刷新）
    if output and output.get('last_draw'):
        draw_data = output['last_draw']
        if draw_data and draw_data.get('geometry') and draw_data['geometry']['type'] == 'Polygon':
            coords = draw_data['geometry']['coordinates'][0]
            points = [(c[0], c[1]) for c in coords]
            if len(points) >= 3 and st.session_state.temp_polygon is None:
                st.session_state.temp_polygon = points
                st.rerun()   # 刷新页面以显示保存表单

# 自动刷新心跳（不影响地图，因为temp_polygon保留了）
time.sleep(0.5)
st.rerun()

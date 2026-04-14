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
    """创建带多边形绘制功能的地图"""
    
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    # 创建地图
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=18,
        control_scale=True,
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德地图'
    )
    
    # 添加备用地图源
    folium.TileLayer(
        'https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        name='高德街道图',
        attr='高德地图',
        control=True
    ).add_to(m)
    
    folium.TileLayer('OpenStreetMap', name='OSM街道图', control=True).add_to(m)
    
    # 添加Home点
    if home_point:
        if coord_system == 'gcj02':
            h_lng, h_lat = home_point[0], home_point[1]
        else:
            h_lng, h_lat = CoordTransform.wgs84_to_gcj02(home_point[0], home_point[1])
        
        folium.Marker(
            [h_lat, h_lng],
            popup=f'🏠 南京科技职业学院',
            icon=folium.Icon(color='green', icon='home', prefix='fa')
        ).add_to(m)
        
        folium.Circle(radius=100, location=[h_lat, h_lng], color='green', fill=True, fill_opacity=0.15, weight=2).add_to(m)
    
    # 添加航点
    if waypoints:
        points = []
        for i, wp in enumerate(waypoints):
            if coord_system == 'gcj02':
                wp_lng, wp_lat = wp[0], wp[1]
            else:
                wp_lng, wp_lat = CoordTransform.wgs84_to_gcj02(wp[0], wp[1])
            
            points.append([wp_lat, wp_lng])
            color = 'blue' if i < len(waypoints)-1 else 'red'
            folium.Marker([wp_lat, wp_lng], popup=f'航点 {i+1}', icon=folium.Icon(color=color, icon='circle', prefix='fa')).add_to(m)
            
            folium.map.Marker(
                [wp_lat, wp_lng],
                icon=folium.DivIcon(
                    icon_size=(24, 24),
                    icon_anchor=(12, 12),
                    html=f'<div style="font-size: 12px; font-weight: bold; background: black; color: white; border-radius: 50%; width: 22px; height: 22px; text-align: center; line-height: 22px;">{i+1}</div>'
                )
            ).add_to(m)
        
        folium.PolyLine(points, color='blue', weight=3, opacity=0.8).add_to(m)
    
    # ========== 添加障碍物（多边形）- 不添加中心标记 ==========
    for i, obstacle in enumerate(obstacles):
        # 转换坐标
        polygon_points = []
        for point in obstacle['points']:
            if coord_system == 'gcj02':
                lng, lat = point[0], point[1]
            else:
                lng, lat = CoordTransform.wgs84_to_gcj02(point[0], point[1])
            polygon_points.append([lat, lng])
        
        # 只绘制多边形，不添加中心标记
        folium.Polygon(
            locations=polygon_points,
            color='red',
            weight=3,
            fill=True,
            fill_opacity=0.4,
            popup=f"🚧 {obstacle['name']}",
            tooltip=f"{obstacle['name']}"
        ).add_to(m)
    
    # 添加多边形绘制工具（Draw插件）
    draw = plugins.Draw(
        draw_options={
            'polygon': {
                'allowIntersection': False,
                'drawError': {'color': '#e1e100', 'message': '多边形不能自相交!'},
                'shapeOptions': {'color': '#ff0000', 'fillColor': '#ff0000', 'fillOpacity': 0.3},
                'repeatMode': True
            },
            'polyline': False,
            'rectangle': False,
            'circle': False,
            'marker': False,
            'circlemarker': False
        },
        edit_options={'edit': True, 'remove': True}
    )
    draw.add_to(m)
    
    # 添加距离圆环
    for r in [50, 100, 200]:
        folium.Circle(radius=r, location=[display_lat, display_lng], color='gray', fill=False, weight=1, opacity=0.4).add_to(m)
    
    folium.LayerControl().add_to(m)
    
    return m

# ==================== 初始化 ====================

if 'heartbeat_mgr' not in st.session_state:
    st.session_state.heartbeat_mgr = HeartbeatManager()
    st.session_state.heartbeat_mgr.start()

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

# 南京科技职业学院坐标
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

# ========== 障碍物存储（带记忆功能） ==========
if 'obstacles' not in st.session_state:
    # 预设一个示例障碍物（教学楼区域）
    st.session_state.obstacles = [
        {
            'id': 0,
            'name': '教学楼A区',
            'points': [
                (118.749000, 32.233800),
                (118.749500, 32.233800),
                (118.749500, 32.234200),
                (118.749000, 32.234200)
            ],
            'created_at': get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
        }
    ]

if 'next_obstacle_id' not in st.session_state:
    st.session_state.next_obstacle_id = 1

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
        
        coord_system = st.selectbox(
            "坐标系",
            options=['wgs84', 'gcj02'],
            format_func=lambda x: 'WGS-84 (GPS坐标)' if x == 'wgs84' else 'GCJ-02 (高德/百度)',
            key="coord_select"
        )
        st.session_state.coord_system = coord_system
        
        st.markdown("---")
        st.subheader("🏠 学校中心点")
        
        home_lng = st.number_input("经度", value=st.session_state.home_point[0], format="%.6f", key="home_lng")
        home_lat = st.number_input("纬度", value=st.session_state.home_point[1], format="%.6f", key="home_lat")
        
        if st.button("更新中心点", key="update_home"):
            st.session_state.home_point = (home_lng, home_lat)
            st.rerun()
        
        st.markdown("---")
        st.subheader("📍 起点 A (教学楼)")
        
        a_lng = st.number_input("经度", value=st.session_state.a_point[0], format="%.6f", key="a_lng")
        a_lat = st.number_input("纬度", value=st.session_state.a_point[1], format="%.6f", key="a_lat")
        
        st.subheader("📍 终点 B (操场)")
        
        b_lng = st.number_input("经度", value=st.session_state.b_point[0], format="%.6f", key="b_lng")
        b_lat = st.number_input("纬度", value=st.session_state.b_point[1], format="%.6f", key="b_lat")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("➕ 生成航线", key="gen_route"):
                st.session_state.a_point = (a_lng, a_lat)
                st.session_state.b_point = (b_lng, b_lat)
                st.session_state.waypoints = [st.session_state.a_point, st.session_state.b_point]
                st.success(f"已生成航线: 教学楼 → 操场")
                st.rerun()
        with col_btn2:
            if st.button("🗑️ 清空航线", key="clear_route"):
                st.session_state.waypoints = []
                st.success("已清空航线")
                st.rerun()
        
        st.markdown("---")
        st.subheader("🚧 障碍物管理")
        
        # 显示当前障碍物数量
        st.info(f"当前障碍物数量: {len(st.session_state.obstacles)}")
        
        st.markdown("---")
        st.subheader("🗑️ 删除障碍物")
        
        if st.session_state.obstacles:
            obs_to_delete = st.selectbox(
                "选择要删除的障碍物",
                options=[f"{i+1}. {o['name']}" for i, o in enumerate(st.session_state.obstacles)],
                key="obs_to_delete"
            )
            
            if st.button("删除选中障碍物", key="delete_obs"):
                idx = int(obs_to_delete.split('.')[0]) - 1
                deleted = st.session_state.obstacles.pop(idx)
                st.success(f"已删除障碍物: {deleted['name']}")
                st.rerun()
        
        if st.button("🗑️ 清空所有障碍物", key="clear_all_obs"):
            st.session_state.obstacles = []
            st.session_state.next_obstacle_id = 0
            st.success("已清空所有障碍物")
            st.rerun()

# ==================== 主内容 ====================

if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控 - 心跳数据")
    st.caption("🕐 所有时间均为北京时间 (UTC+8)")
    
    heartbeats, seq, last_time = st.session_state.heartbeat_mgr.get_data()
    
    if heartbeats:
        df = pd.DataFrame(heartbeats)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总心跳数", len(df))
        with col2:
            st.metric("当前序列号", seq)
        
        if len(heartbeats) >= 2:
            intervals = []
            for i in range(1, len(heartbeats)):
                intervals.append(heartbeats[i]['timestamp'] - heartbeats[i-1]['timestamp'])
            avg_interval = sum(intervals) / len(intervals)
            st.metric("平均间隔", f"{avg_interval:.3f}秒")
        
        status, time_since = st.session_state.heartbeat_mgr.get_connection_status()
        
        with col3:
            if status == "在线":
                st.metric("连接状态", "✅ 在线")
            else:
                st.metric("连接状态", "❌ 离线")
        
        with col4:
            expected = seq
            received = len(df)
            loss_rate = (expected - received) / expected * 100 if expected > 0 else 0
            st.metric("丢包率", f"{loss_rate:.1f}%")
        
        if status == "超时":
            st.error(f"⚠️ 连接超时！已 {time_since:.1f} 秒未收到心跳")
        
        # 心跳间隔分析图
        if len(heartbeats) >= 2:
            fig_interval = go.Figure()
            intervals_data = []
            seqs = []
            for i in range(1, len(heartbeats)):
                intervals_data.append(heartbeats[i]['timestamp'] - heartbeats[i-1]['timestamp'])
                seqs.append(heartbeats[i]['seq'])
            
            fig_interval.add_trace(go.Scatter(
                x=seqs,
                y=intervals_data,
                mode='lines+markers',
                name='心跳间隔',
                line=dict(color='orange', width=2),
                marker=dict(size=6, color='red')
            ))
            fig_interval.add_hline(y=1.0, line_dash="dash", line_color="green", annotation_text="目标间隔1秒")
            fig_interval.update_layout(
                title="心跳间隔精确度分析",
                xaxis_title="序列号",
                yaxis_title="间隔 (秒)",
                height=300
            )
            st.plotly_chart(fig_interval, use_container_width=True)
        
        # 心跳趋势图
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['time'],
            y=df['seq'],
            mode='lines+markers',
            name='心跳',
            line=dict(color='blue', width=2),
            marker=dict(size=6, color='red')
        ))
        fig.update_layout(
            title="心跳序列号趋势",
            xaxis_title="北京时间",
            yaxis_title="序列号",
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 详细数据表格
        st.subheader("📋 详细心跳数据")
        display_df = df[['time_ms', 'seq']].tail(20).copy()
        display_df.columns = ['北京时间 (精确到毫秒)', '序列号']
        st.dataframe(display_df, use_container_width=True)
        
        latest = heartbeats[-1]
        st.success(f"✅ 最新心跳时间: {latest['time_ms']} (北京时间) | 序列号: {latest['seq']}")
        now_beijing = get_beijing_time()
        st.caption(f"🕐 当前北京时间: {now_beijing.strftime('%Y年%m月%d日 %H:%M:%S')}")
    else:
        st.info("等待心跳数据...")

else:
    # ==================== 航线规划页面 ====================
    st.header("🗺️ 航线规划 - 南京科技职业学院")
    st.caption("🎨 使用右侧工具栏的多边形工具绘制障碍物区域（红色区域）")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"🏫 学校: 南京科技职业学院")
        st.info(f"📍 中心点: {st.session_state.home_point[0]:.6f}, {st.session_state.home_point[1]:.6f}")
    with col2:
        if st.session_state.waypoints:
            st.success(f"✈️ 当前航线: 教学楼 → 操场")
            st.success(f"航点数: {len(st.session_state.waypoints)}")
        else:
            st.warning("⚠️ 暂无航线，请设置起点和终点后点击「生成航线」")
        
        # 显示障碍物统计
        st.info(f"🚧 障碍物数量: {len(st.session_state.obstacles)}")
    
    st.markdown("---")
    
    # 显示地图（带绘制工具）
    with st.spinner("加载高德卫星地图..."):
        try:
            if st.session_state.waypoints:
                all_points = [st.session_state.home_point] + st.session_state.waypoints
                center_lng = sum(p[0] for p in all_points) / len(all_points)
                center_lat = sum(p[1] for p in all_points) / len(all_points)
            else:
                center_lng, center_lat = st.session_state.home_point
            
            m = create_map_with_drawing(
                center_lng,
                center_lat,
                st.session_state.waypoints,
                st.session_state.home_point,
                st.session_state.obstacles,
                st.session_state.coord_system
            )
            
            # 显示地图并获取绘制数据
            output = st_folium(m, width=1000, height=600, returned_objects=["last_draw"])
            
            # 处理绘制完成的多边形
            if output and output.get('last_draw') is not None:
                draw_data = output['last_draw']
                if draw_data and draw_data.get('geometry') and draw_data['geometry'].get('type') == 'Polygon':
                    # 获取多边形顶点坐标
                    coordinates = draw_data['geometry']['coordinates'][0]
                    # 转换为 (lng, lat) 格式
                    points = [(coord[0], coord[1]) for coord in coordinates]
                    
                    # 保存障碍物
                    new_obstacle = {
                        'id': st.session_state.next_obstacle_id,
                        'name': f"障碍物{st.session_state.next_obstacle_id + 1}",
                        'points': points,
                        'created_at': get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    st.session_state.obstacles.append(new_obstacle)
                    st.session_state.next_obstacle_id += 1
                    st.success(f"✅ 已添加障碍物: {new_obstacle['name']}")
                    st.rerun()
            
            st.success("✅ 高德卫星地图加载成功")
            st.caption("📸 地图类型：高德卫星图 + 道路标注")
            st.info("🎨 使用地图右上角的绘制工具，点击多边形图标后在地图上点击画区域，双击完成绘制")
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
            st.info("请刷新页面重试")
    
    # 显示障碍物列表
    if st.session_state.obstacles:
        st.markdown("---")
        st.subheader("🚧 当前障碍物列表")
        
        for i, obs in enumerate(st.session_state.obstacles):
            with st.expander(f"障碍物 {i+1}: {obs['name']}"):
                st.write(f"**创建时间:** {obs['created_at']}")
                st.write(f"**顶点数量:** {len(obs['points'])} 个")
                st.write(f"**顶点坐标:**")
                for j, point in enumerate(obs['points']):
                    st.write(f"  - 点{j+1}: ({point[0]:.6f}, {point[1]:.6f})")
    
    # 航线信息
    if st.session_state.waypoints and len(st.session_state.waypoints) >= 2:
        st.markdown("---")
        st.subheader("📊 航线信息")
        
        a = st.session_state.waypoints[0]
        b = st.session_state.waypoints[-1]
        
        dx = (b[0] - a[0]) * 111000 * math.cos(math.radians((a[1] + b[1]) / 2))
        dy = (b[1] - a[1]) * 111000
        distance = math.sqrt(dx*dx + dy*dy)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("起点 A (教学楼)", f"{a[0]:.6f}, {a[1]:.6f}")
        with col2:
            st.metric("终点 B (操场)", f"{b[0]:.6f}, {b[1]:.6f}")
        with col3:
            st.metric("直线距离", f"{distance:.1f} 米")

# 每0.5秒刷新页面
time.sleep(0.5)
st.rerun() 

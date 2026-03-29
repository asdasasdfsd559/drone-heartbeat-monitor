import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
from datetime import datetime
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="无人机地面站", layout="wide")

# ==================== 坐标系转换 ====================

class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003
    
    @staticmethod
    def gcj02_to_wgs84(lng, lat):
        return lng - 0.0005, lat - 0.0003

# ==================== 地图函数 ====================

def create_map(center_lng, center_lat, waypoints, home_point, coord_system):
    """创建地面站地图"""
    
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    # 使用国内可访问的 CartoDB 地图源
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=17,
        control_scale=True,
        tiles='CartoDB positron'
    )
    
    # 添加备用地图源
    folium.TileLayer('OpenStreetMap', name='标准地图').add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='深色地图').add_to(m)
    
    # 添加Home点
    if home_point:
        if coord_system == 'gcj02':
            h_lng, h_lat = home_point[0] + 0.0005, home_point[1] + 0.0003
        else:
            h_lng, h_lat = home_point[0], home_point[1]
        
        folium.Marker(
            [h_lat, h_lng],
            popup=f'🏠 HOME<br>{h_lng:.6f}, {h_lat:.6f}',
            icon=folium.Icon(color='green', icon='home', prefix='fa')
        ).add_to(m)
        
        folium.Circle(
            radius=50,
            location=[h_lat, h_lng],
            color='green',
            fill=True,
            fill_opacity=0.2,
            weight=2
        ).add_to(m)
    
    # 添加航点
    if waypoints:
        points = []
        for i, wp in enumerate(waypoints):
            if coord_system == 'gcj02':
                wp_lng, wp_lat = wp[0] + 0.0005, wp[1] + 0.0003
            else:
                wp_lng, wp_lat = wp[0], wp[1]
            
            points.append([wp_lat, wp_lng])
            
            color = 'blue' if i < len(waypoints)-1 else 'red'
            folium.Marker(
                [wp_lat, wp_lng],
                popup=f'WP{i+1}<br>{wp_lng:.6f}, {wp_lat:.6f}',
                icon=folium.Icon(color=color, icon='circle', prefix='fa')
            ).add_to(m)
            
            # 数字标签
            folium.map.Marker(
                [wp_lat, wp_lng],
                icon=folium.DivIcon(
                    icon_size=(24, 24),
                    icon_anchor=(12, 12),
                    html=f'<div style="font-size: 12px; font-weight: bold; background: black; color: white; border-radius: 50%; width: 22px; height: 22px; text-align: center; line-height: 22px;">{i+1}</div>'
                )
            ).add_to(m)
        
        # 航线
        folium.PolyLine(points, color='blue', weight=3, opacity=0.8).add_to(m)
    
    # 添加距离圆环
    for r in [50, 100, 200]:
        folium.Circle(
            radius=r,
            location=[display_lat, display_lng],
            color='gray',
            fill=False,
            weight=1,
            opacity=0.5
        ).add_to(m)
    
    folium.LayerControl().add_to(m)
    
    return m

# ==================== 初始化所有状态 ====================

# 页面状态
if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

# 心跳数据
if 'heartbeats' not in st.session_state:
    st.session_state.heartbeats = []
    st.session_state.sequence = 0
    st.session_state.last_time = datetime.now()

# 地图数据 - 南京某学校坐标
if 'home_point' not in st.session_state:
    st.session_state.home_point = (118.767413, 32.041544)

if 'waypoints' not in st.session_state:
    st.session_state.waypoints = []

if 'a_point' not in st.session_state:
    st.session_state.a_point = (118.767413, 32.041544)

if 'b_point' not in st.session_state:
    st.session_state.b_point = (118.768413, 32.042544)

if 'coord_system' not in st.session_state:
    st.session_state.coord_system = 'wgs84'

# ==================== 自动生成心跳 ====================

current_time = datetime.now()
time_diff = (current_time - st.session_state.last_time).total_seconds()

if time_diff >= 1:
    st.session_state.sequence += 1
    st.session_state.heartbeats.append({
        'time': current_time.strftime("%H:%M:%S"),
        'seq': st.session_state.sequence
    })
    if len(st.session_state.heartbeats) > 100:
        st.session_state.heartbeats.pop(0)
    st.session_state.last_time = current_time

# ==================== 侧边栏 ====================

with st.sidebar:
    st.title("🎮 无人机地面站")
    
    selected_page = st.radio(
        "选择功能",
        ["📡 飞行监控", "🗺️ 航线规划"],
        index=0 if st.session_state.page == "飞行监控" else 1
    )
    st.session_state.page = selected_page
    
    st.markdown("---")
    
    # 心跳状态
    if st.session_state.heartbeats:
        last_time_str = st.session_state.heartbeats[-1]['time']
        last_heartbeat = datetime.strptime(last_time_str, "%H:%M:%S")
        now = datetime.now()
        time_since = (now - last_heartbeat.replace(year=now.year, month=now.month, day=now.day)).seconds
        
        if time_since < 3:
            st.success(f"✅ 心跳正常 ({time_since}秒)")
            st.metric("当前序列号", st.session_state.heartbeats[-1]['seq'])
        else:
            st.error(f"❌ 超时！{time_since}秒无心跳")
    
    # 航线规划设置
    if "🗺️ 航线规划" in st.session_state.page:
        st.markdown("---")
        
        # 坐标系选择
        coord_system = st.selectbox(
            "坐标系",
            options=['wgs84', 'gcj02'],
            format_func=lambda x: 'WGS-84 (GPS坐标)' if x == 'wgs84' else 'GCJ-02 (高德/百度)'
        )
        st.session_state.coord_system = coord_system
        
        st.markdown("---")
        st.subheader("🏠 起飞点 (Home)")
        
        col1, col2 = st.columns(2)
        with col1:
            home_lng = st.number_input("经度", value=st.session_state.home_point[0], format="%.6f")
        with col2:
            home_lat = st.number_input("纬度", value=st.session_state.home_point[1], format="%.6f")
        
        if st.button("更新 Home 点"):
            st.session_state.home_point = (home_lng, home_lat)
            st.rerun()
        
        st.markdown("---")
        st.subheader("📍 起点 A")
        
        col3, col4 = st.columns(2)
        with col3:
            a_lng = st.number_input("经度", value=st.session_state.a_point[0], format="%.6f")
        with col4:
            a_lat = st.number_input("纬度", value=st.session_state.a_point[1], format="%.6f")
        
        st.subheader("📍 终点 B")
        
        col5, col6 = st.columns(2)
        with col5:
            b_lng = st.number_input("经度", value=st.session_state.b_point[0], format="%.6f")
        with col6:
            b_lat = st.number_input("纬度", value=st.session_state.b_point[1], format="%.6f")
        
        col7, col8 = st.columns(2)
        with col7:
            if st.button("➕ 生成航线"):
                st.session_state.a_point = (a_lng, a_lat)
                st.session_state.b_point = (b_lng, b_lat)
                st.session_state.waypoints = [st.session_state.a_point, st.session_state.b_point]
                st.success(f"已生成航线: A→B")
                st.rerun()
        with col8:
            if st.button("🗑️ 清空航线"):
                st.session_state.waypoints = []
                st.success("已清空航线")
                st.rerun()

# ==================== 主内容 ====================

if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控")
    
    if st.session_state.heartbeats:
        df = pd.DataFrame(st.session_state.heartbeats)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总心跳数", len(df))
        with col2:
            st.metric("当前序列号", df['seq'].iloc[-1])
        
        last_time_str = df['time'].iloc[-1]
        last_heartbeat = datetime.strptime(last_time_str, "%H:%M:%S")
        now = datetime.now()
        time_since = (now - last_heartbeat.replace(year=now.year, month=now.month, day=now.day)).seconds
        
        with col3:
            if time_since < 3:
                st.metric("连接状态", "✅ 在线")
            else:
                st.metric("连接状态", "❌ 离线")
        
        with col4:
            expected = df['seq'].iloc[-1]
            received = len(df)
            loss_rate = (expected - received) / expected * 100 if expected > 0 else 0
            st.metric("丢包率", f"{loss_rate:.1f}%")
        
        if time_since >= 3:
            st.error(f"⚠️ 连接超时！{time_since}秒未收到心跳")
        
        # 图表
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
            xaxis_title="时间",
            yaxis_title="序列号",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📋 详细数据"):
            st.dataframe(df.tail(20), use_container_width=True)
    else:
        st.info("等待心跳数据...")

else:
    # 航线规划页面
    st.header("🗺️ 航线规划")
    
    # 显示当前信息
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"🏠 Home点: {st.session_state.home_point[0]:.6f}, {st.session_state.home_point[1]:.6f}")
    with col2:
        if st.session_state.waypoints:
            st.success(f"✈️ 当前航线: A→B ({len(st.session_state.waypoints)}个航点)")
        else:
            st.warning("⚠️ 暂无航线，请设置A点和B点后点击「生成航线」")
    
    st.markdown("---")
    
    # 显示地图
    with st.spinner("加载地图中..."):
        try:
            # 计算地图中心点
            if st.session_state.waypoints:
                all_points = [st.session_state.home_point] + st.session_state.waypoints
                center_lng = sum(p[0] for p in all_points) / len(all_points)
                center_lat = sum(p[1] for p in all_points) / len(all_points)
            else:
                center_lng, center_lat = st.session_state.home_point
            
            m = create_map(
                center_lng,
                center_lat,
                st.session_state.waypoints,
                st.session_state.home_point,
                st.session_state.coord_system
            )
            
            st_folium(m, width=1000, height=600)
            st.success("✅ 地图加载成功")
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
            st.info("请检查网络连接后刷新页面")
    
    # 显示航线信息
    if st.session_state.waypoints and len(st.session_state.waypoints) >= 2:
        st.markdown("---")
        st.subheader("📊 航线信息")
        
        # 计算A到B的距离
        a = st.session_state.waypoints[0]
        b = st.session_state.waypoints[-1]
        
        dx = (b[0] - a[0]) * 111000 * math.cos(math.radians((a[1] + b[1]) / 2))
        dy = (b[1] - a[1]) * 111000
        distance = math.sqrt(dx*dx + dy*dy)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("起点 A", f"{a[0]:.6f}, {a[1]:.6f}")
        with col2:
            st.metric("终点 B", f"{b[0]:.6f}, {b[1]:.6f}")
        with col3:
            st.metric("直线距离", f"{distance:.1f} 米")
        
        st.caption("💡 地图上的红色方块就是建筑物（障碍物），航线需要避开它们")

# 自动刷新心跳
time.sleep(1)
st.rerun()

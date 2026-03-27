import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime
import folium
from streamlit_folium import st_folium
import math

st.set_page_config(page_title="无人机综合监控系统", layout="wide")

# ==================== 坐标系转换 ====================

class CoordTransform:
    """WGS-84 和 GCJ-02 坐标系转换"""
    
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003
    
    @staticmethod
    def gcj02_to_wgs84(lng, lat):
        return lng - 0.0005, lat - 0.0003

# ==================== 地图函数 ====================

def create_real_map(center_lng, center_lat, waypoints, coord_system):
    """创建真实地图"""
    
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=17,
        control_scale=True
    )
    
    folium.Marker(
        [display_lat, display_lng],
        popup="起飞点/中心点",
        icon=folium.Icon(color='red')
    ).add_to(m)
    
    if waypoints:
        points = []
        for wp in waypoints:
            if coord_system == 'gcj02':
                wp_lng, wp_lat = wp['lng'] + 0.0005, wp['lat'] + 0.0003
            else:
                wp_lng, wp_lat = wp['lng'], wp['lat']
            
            points.append([wp_lat, wp_lng])
            
            folium.Marker(
                [wp_lat, wp_lng],
                popup=f"航点 {wp['id']+1}<br>高度: {wp['altitude']}m",
                icon=folium.Icon(color='blue')
            ).add_to(m)
        
        folium.PolyLine(points, color='blue', weight=3, opacity=0.8).add_to(m)
    
    return m

def create_waypoints(center_lng, center_lat):
    """生成航线航点"""
    waypoints = []
    radius = 0.002
    num_points = 8
    
    for i in range(num_points):
        angle = i * (360 / num_points)
        rad = math.radians(angle)
        lng = center_lng + radius * math.cos(rad)
        lat = center_lat + radius * math.sin(rad)
        
        waypoints.append({
            'id': i,
            'lng': lng,
            'lat': lat,
            'altitude': 100,
            'action': 'fly' if i < num_points - 1 else 'land'
        })
    
    return waypoints

# ==================== 初始化数据 ====================

# 初始化页面状态
if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

# 初始化心跳数据
if 'heartbeats' not in st.session_state:
    st.session_state.heartbeats = []
    st.session_state.sequence = 0
    st.session_state.last_time = datetime.now()

# 初始化航线数据
if 'center_lng' not in st.session_state:
    st.session_state.center_lng = 118.767413
    st.session_state.center_lat = 32.041544
    st.session_state.waypoints = create_waypoints(
        st.session_state.center_lng, 
        st.session_state.center_lat
    )
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
    st.title("🎮 控制面板")
    
    # 页面选择
    selected_page = st.radio(
        "选择功能",
        ["飞行监控", "航线监测"],
        index=0 if st.session_state.page == "飞行监控" else 1
    )
    st.session_state.page = selected_page
    
    st.markdown("---")
    
    # 心跳状态显示
    if st.session_state.heartbeats:
        last_time_str = st.session_state.heartbeats[-1]['time']
        last_heartbeat = datetime.strptime(last_time_str, "%H:%M:%S")
        now = datetime.now()
        time_since = (now - last_heartbeat.replace(year=now.year, month=now.month, day=now.day)).seconds
        
        if time_since < 3:
            st.success(f"✅ 连接正常 (最后心跳: {time_since}秒前)")
        else:
            st.error(f"❌ 连接超时！{time_since}秒未收到心跳")
    
    # 航线监测页面的设置
    if st.session_state.page == "航线监测":
        st.markdown("---")
        
        coord_system = st.selectbox(
            "坐标系",
            options=['wgs84', 'gcj02'],
            format_func=lambda x: 'WGS-84 (GPS坐标)' if x == 'wgs84' else 'GCJ-02 (高德/百度地图)'
        )
        st.session_state.coord_system = coord_system
        
        st.markdown("---")
        st.subheader("航线位置")
        center_lng = st.number_input("经度", value=st.session_state.center_lng, format="%.6f")
        center_lat = st.number_input("纬度", value=st.session_state.center_lat, format="%.6f")
        
        if st.button("更新航线"):
            st.session_state.center_lng = center_lng
            st.session_state.center_lat = center_lat
            st.session_state.waypoints = create_waypoints(center_lng, center_lat)
            st.rerun()

# ==================== 主内容区域 ====================

if st.session_state.page == "飞行监控":
    # 飞行监控页面
    st.header("📡 飞行监控 - 心跳数据")
    
    if st.session_state.heartbeats:
        df = pd.DataFrame(st.session_state.heartbeats)
        
        # 统计卡片
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("总心跳数", len(df))
        
        with col2:
            st.metric("当前序列号", df['seq'].iloc[-1])
        
        # 检查超时（3秒）
        last_time_str = df['time'].iloc[-1]
        last_heartbeat = datetime.strptime(last_time_str, "%H:%M:%S")
        now = datetime.now()
        time_since = (now - last_heartbeat.replace(year=now.year, month=now.month, day=now.day)).seconds
        
        with col3:
            if time_since < 3:
                st.metric("连接状态", "✅ 在线")
            else:
                st.metric("连接状态", "❌ 离线")
                st.error(f"⚠️ 超时！{time_since}秒未收到心跳")
        
        # 绘制图表
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['time'],
            y=df['seq'],
            mode='lines+markers',
            name='心跳',
            line=dict(color='blue', width=2),
            marker=dict(size=8, color='red')
        ))
        
        fig.update_layout(
            title="心跳序列号变化",
            xaxis_title="时间",
            yaxis_title="序列号",
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 数据表
        with st.expander("查看详细数据"):
            st.dataframe(df.tail(20), use_container_width=True)
    else:
        st.info("等待数据生成...")

else:
    # 航线监测页面
    st.header("🗺️ 航线监测")
    
    # 显示航线统计
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("航点数量", len(st.session_state.waypoints))
    with col2:
        st.metric("飞行高度", "100 米")
    with col3:
        st.metric("航线半径", "约200 米")
    with col4:
        total_dist = len(st.session_state.waypoints) * 314
        st.metric("总航线距离", f"{total_dist:.0f} 米")
    
    st.markdown("---")
    
    # 显示真实地图
    m = create_real_map(
        st.session_state.center_lng,
        st.session_state.center_lat,
        st.session_state.waypoints,
        st.session_state.coord_system
    )
    
    st_folium(m, width=900, height=600)
    
    # 说明
    st.info("📍 地图显示真实地理信息（OpenStreetMap）")
    st.caption("💡 地图上的建筑、道路都是真实存在的，缩放地图可以看到周围的真实建筑")
    
    # 航点详情表格
    st.markdown("---")
    st.subheader("📋 航点详情")
    waypoints_df = pd.DataFrame(st.session_state.waypoints)
    waypoints_df['经度'] = waypoints_df['lng'].apply(lambda x: f"{x:.6f}")
    waypoints_df['纬度'] = waypoints_df['lat'].apply(lambda x: f"{x:.6f}")
    st.dataframe(waypoints_df[['id', '经度', '纬度', 'altitude', 'action']], 
                use_container_width=True)

# ==================== 自动刷新 ====================

# 等待1秒后自动刷新（让心跳数据更新）
time.sleep(1)
st.rerun()

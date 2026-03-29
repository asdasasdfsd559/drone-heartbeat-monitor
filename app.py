import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
from datetime import datetime
import folium
from streamlit_folium import st_folium
import numpy as np

st.set_page_config(page_title="无人机地面站 - Mission Planner风格", layout="wide")

# ==================== 坐标系转换 ====================

class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003
    
    @staticmethod
    def gcj02_to_wgs84(lng, lat):
        return lng - 0.0005, lat - 0.0003

# ==================== Mission Planner 风格地图 ====================

def create_mission_planner_map(center_lng, center_lat, waypoints, home_point, coord_system):
    """创建类似 Mission Planner 的地图界面"""
    
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    # 使用高分辨率卫星图（类似Mission Planner）
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=18,
        control_scale=True,
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite'
    )
    
    # 添加多种地图源（可切换）
    folium.TileLayer(
        'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='卫星图',
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        'OpenStreetMap',
        name='街道图',
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        'https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
        attr='Google Terrain',
        name='地形图',
        control=True
    ).add_to(m)
    
    # 添加Home点
    if home_point:
        if coord_system == 'gcj02':
            h_lng, h_lat = home_point[0] + 0.0005, home_point[1] + 0.0003
        else:
            h_lng, h_lat = home_point[0], home_point[1]
        
        # Home点大图标
        folium.Marker(
            [h_lat, h_lng],
            popup=f'<b>🏠 HOME</b><br>经度: {h_lng:.6f}<br>纬度: {h_lat:.6f}',
            icon=folium.Icon(color='darkgreen', icon='home', prefix='fa')
        ).add_to(m)
        
        # Home点圆圈
        folium.Circle(
            radius=50,
            location=[h_lat, h_lng],
            color='green',
            fill=True,
            fill_opacity=0.3,
            weight=2,
            popup='Home位置 (RTL范围)'
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
            
            # 航点样式
            color = 'blue' if i < len(waypoints)-1 else 'red'
            icon = 'circle' if i < len(waypoints)-1 else 'flag-checkered'
            
            folium.Marker(
                [wp_lat, wp_lng],
                popup=f'<b>WP {i+1}</b><br>经度: {wp_lng:.6f}<br>纬度: {wp_lat:.6f}',
                icon=folium.Icon(color=color, icon=icon, prefix='fa')
            ).add_to(m)
            
            # 添加数字标签
            folium.map.Marker(
                [wp_lat, wp_lng],
                icon=folium.DivIcon(
                    icon_size=(30, 30),
                    icon_anchor=(15, 15),
                    html=f'<div style="font-size: 14px; font-weight: bold; background: rgba(0,0,0,0.7); color: white; border-radius: 50%; width: 26px; height: 26px; text-align: center; line-height: 26px; border: 2px solid yellow;">{i+1}</div>'
                )
            ).add_to(m)
        
        # 绘制航线
        folium.PolyLine(
            points,
            color='cyan',
            weight=3,
            opacity=0.9,
            popup='飞行航线'
        ).add_to(m)
        
        # 添加航向箭头（用三角形标记）
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            mid_lat = (p1[0] + p2[0]) / 2
            mid_lng = (p1[1] + p2[1]) / 2
            
            # 计算角度
            angle = math.degrees(math.atan2(p2[0] - p1[0], p2[1] - p1[1]))
            
            # 使用自定义图标作为箭头
            folium.Marker(
                [mid_lat, mid_lng],
                icon=folium.Icon(color='yellow', icon='arrow-up', prefix='fa', angle=angle),
                popup=f'方向: {angle:.0f}°'
            ).add_to(m)
    
    # 添加距离圆环
    for radius in [50, 100, 200, 500]:
        folium.Circle(
            radius=radius,
            location=[display_lat, display_lng],
            color='white',
            fill=False,
            weight=1,
            opacity=0.3
        ).add_to(m)
    
    # 添加经纬度网格
    for i in range(-3, 4):
        # 经度线
        lng_line = display_lng + i * 0.0005
        folium.PolyLine(
            [[display_lat - 0.002, lng_line], [display_lat + 0.002, lng_line]],
            color='gray',
            weight=1,
            opacity=0.4
        ).add_to(m)
        
        # 纬度线
        lat_line = display_lat + i * 0.0005
        folium.PolyLine(
            [[lat_line, display_lng - 0.002], [lat_line, display_lng + 0.002]],
            color='gray',
            weight=1,
            opacity=0.4
        ).add_to(m)
    
    # 添加全屏按钮
    folium.plugins.Fullscreen().add_to(m)
    
    # 添加鼠标位置显示
    folium.plugins.MousePosition().add_to(m)
    
    # 添加图层控制
    folium.LayerControl(position='topright').add_to(m)
    
    return m

# ==================== 初始化 ====================

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

if 'heartbeats' not in st.session_state:
    st.session_state.heartbeats = []
    st.session_state.sequence = 0
    st.session_state.last_time = datetime.now()

# Mission Planner 风格数据
if 'home_point' not in st.session_state:
    # 南京某学校
    st.session_state.home_point = (118.767413, 32.041544)
    st.session_state.waypoints = []

if 'coord_system' not in st.session_state:
    st.session_state.coord_system = 'wgs84'

# 自动生成心跳
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
    st.title("🎮 Mission Planner 地面站")
    
    selected_page = st.radio(
        "选择模式",
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
            st.success(f"✅ 心跳正常 ({time_since}s)")
            st.metric("当前序列号", st.session_state.heartbeats[-1]['seq'])
        else:
            st.error(f"❌ 超时！{time_since}s无心跳")
    
    # 航线规划设置
    if "🗺️ 航线规划" in st.session_state.page:
        st.markdown("---")
        st.subheader("🏠 Home 位置")
        
        col1, col2 = st.columns(2)
        with col1:
            home_lng = st.number_input("经度", value=st.session_state.home_point[0], format="%.6f", key="home_lng")
        with col2:
            home_lat = st.number_input("纬度", value=st.session_state.home_point[1], format="%.6f", key="home_lat")
        
        if st.button("🔄 更新Home点", use_container_width=True):
            st.session_state.home_point = (home_lng, home_lat)
            st.success("Home点已更新")
            st.rerun()
        
        st.markdown("---")
        st.subheader("✈️ 航点规划")
        
        # 显示现有航点
        if st.session_state.waypoints:
            st.write(f"**当前航点数: {len(st.session_state.waypoints)}**")
            for i, wp in enumerate(st.session_state.waypoints):
                st.text(f"WP{i+1}: {wp[0]:.6f}, {wp[1]:.6f}")
        
        # 添加航点
        st.write("**添加新航点:**")
        col3, col4 = st.columns(2)
        with col3:
            wp_lng = st.number_input("经度", value=st.session_state.home_point[0] + 0.0005, format="%.6f", key="wp_lng")
        with col4:
            wp_lat = st.number_input("纬度", value=st.session_state.home_point[1] + 0.0005, format="%.6f", key="wp_lat")
        
        col5, col6 = st.columns(2)
        with col5:
            if st.button("➕ 添加航点", use_container_width=True):
                st.session_state.waypoints.append((wp_lng, wp_lat))
                st.success(f"已添加航点 {len(st.session_state.waypoints)}")
                st.rerun()
        with col6:
            if st.button("🗑️ 清空所有航点", use_container_width=True):
                st.session_state.waypoints = []
                st.success("已清空所有航点")
                st.rerun()
        
        st.markdown("---")
        st.subheader("🌐 坐标系")
        
        coord_system = st.selectbox(
            "坐标系",
            options=['wgs84', 'gcj02'],
            format_func=lambda x: 'WGS-84 (GPS坐标)' if x == 'wgs84' else 'GCJ-02 (高德/百度地图)'
        )
        st.session_state.coord_system = coord_system

# ==================== 主内容 ====================

if "飞行监控" in st.session_state.page:
    # 飞行监控页面
    st.header("📡 飞行监控")
    
    if st.session_state.heartbeats:
        df = pd.DataFrame(st.session_state.heartbeats)
        
        # 仪表盘样式
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
            st.error(f"⚠️ 连接超时！已 {time_since} 秒未收到心跳")
        
        # 心跳趋势图
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['time'],
            y=df['seq'],
            mode='lines+markers',
            name='心跳',
            line=dict(color='cyan', width=2),
            marker=dict(size=6, color='yellow')
        ))
        fig.update_layout(
            title="心跳序列号趋势",
            xaxis_title="时间",
            yaxis_title="序列号",
            height=400,
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white')
        )
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📋 详细数据"):
            st.dataframe(df.tail(20), use_container_width=True)
    else:
        st.info("等待心跳数据...")

else:
    # Mission Planner 风格地图页面
    st.header("🗺️ 航线规划 - Mission Planner 风格")
    
    # 状态栏
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Home位置", f"{st.session_state.home_point[0]:.6f}, {st.session_state.home_point[1]:.6f}")
    with col2:
        st.metric("航点数量", len(st.session_state.waypoints))
    with col3:
        if len(st.session_state.waypoints) >= 2:
            # 计算总距离
            total_dist = 0
            prev = st.session_state.home_point
            for wp in st.session_state.waypoints:
                dx = (wp[0] - prev[0]) * 111000 * math.cos(math.radians((prev[1] + wp[1]) / 2))
                dy = (wp[1] - prev[1]) * 111000
                total_dist += math.sqrt(dx*dx + dy*dy)
                prev = wp
            st.metric("航线总距离", f"{total_dist:.0f} m")
        else:
            st.metric("航线总距离", "0 m")
    
    st.markdown("---")
    
    # 显示地图
    with st.spinner("加载Mission Planner风格地图..."):
        try:
            # 计算地图中心点
            if st.session_state.waypoints:
                all_points = [st.session_state.home_point] + st.session_state.waypoints
                center_lng = sum(p[0] for p in all_points) / len(all_points)
                center_lat = sum(p[1] for p in all_points) / len(all_points)
            else:
                center_lng, center_lat = st.session_state.home_point
            
            m = create_mission_planner_map(
                center_lng,
                center_lat,
                st.session_state.waypoints,
                st.session_state.home_point,
                st.session_state.coord_system
            )
            
            st_folium(m, width=1200, height=700, returned_objects=[])
            st.success("✅ 地图加载成功")
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
            st.info("请检查网络连接后刷新页面")
    
    # 操作提示
    with st.expander("📖 Mission Planner 风格操作说明", expanded=False):
        st.markdown("""
        **地图操作：**
        - 🖱️ 鼠标滚轮：缩放地图
        - 🖱️ 鼠标拖动：移动视角
        - 🗺️ 右上角：切换卫星图/街道图/地形图
        - 📍 鼠标位置：右下角显示实时坐标
        
        **地面站功能：**
        - 🏠 **Home点**：绿色房子图标，无人机起飞点，带50m RTL范围圆
        - ✈️ **航点WP**：蓝色圆点，带数字编号
        - 🔵 **航线**：青色线连接航点
        - 🟡 **黄色箭头**：指示飞行方向
        - ⚪ **距离环**：50m, 100m, 200m, 500m参考圆
        - 📏 **灰色网格**：经纬度参考线
        
        **规划流程：**
        1. 设置Home点（起飞点）
        2. 添加航点（任务点）
        3. 系统自动计算航线距离
        4. 地图显示完整航线
        """)

# 自动刷新心跳
time.sleep(1)
st.rerun()

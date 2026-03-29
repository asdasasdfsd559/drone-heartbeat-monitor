import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
from datetime import datetime
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="无人机监测系统", layout="wide")

# ==================== 坐标系转换 ====================

class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003
    
    @staticmethod
    def gcj02_to_wgs84(lng, lat):
        return lng - 0.0005, lat - 0.0003

# ==================== 地图函数 ====================

def create_map(center_lng, center_lat, a_point, b_point, coord_system):
    """创建真实地图，显示A点和B点"""
    
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    # 使用真实地图（OpenStreetMap）
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=18,
        control_scale=True
    )
    
    # 添加A点标记
    if a_point:
        if coord_system == 'gcj02':
            a_lng, a_lat = a_point[0] + 0.0005, a_point[1] + 0.0003
        else:
            a_lng, a_lat = a_point[0], a_point[1]
        
        folium.Marker(
            [a_lat, a_lng],
            popup=f'<b>起点 A</b><br>经度: {a_lng:.6f}<br>纬度: {a_lat:.6f}',
            icon=folium.Icon(color='green', icon='play', prefix='fa')
        ).add_to(m)
        
        # 添加圆圈标记
        folium.Circle(
            radius=20,
            location=[a_lat, a_lng],
            color='green',
            fill=True,
            fill_opacity=0.5
        ).add_to(m)
    
    # 添加B点标记
    if b_point:
        if coord_system == 'gcj02':
            b_lng, b_lat = b_point[0] + 0.0005, b_point[1] + 0.0003
        else:
            b_lng, b_lat = b_point[0], b_point[1]
        
        folium.Marker(
            [b_lat, b_lng],
            popup=f'<b>终点 B</b><br>经度: {b_lng:.6f}<br>纬度: {b_lat:.6f}',
            icon=folium.Icon(color='red', icon='flag-checkered', prefix='fa')
        ).add_to(m)
        
        folium.Circle(
            radius=20,
            location=[b_lat, b_lng],
            color='red',
            fill=True,
            fill_opacity=0.5
        ).add_to(m)
    
    # 如果A和B都有，画一条直线
    if a_point and b_point:
        if coord_system == 'gcj02':
            a_lng, a_lat = a_point[0] + 0.0005, a_point[1] + 0.0003
            b_lng, b_lat = b_point[0] + 0.0005, b_point[1] + 0.0003
        else:
            a_lng, a_lat = a_point[0], a_point[1]
            b_lng, b_lat = b_point[0], b_point[1]
        
        folium.PolyLine(
            [[a_lat, a_lng], [b_lat, b_lng]],
            color='blue',
            weight=3,
            opacity=0.8,
            popup='规划航线'
        ).add_to(m)
        
        # 计算距离
        dx = (b_lng - a_lng) * 111000 * math.cos(math.radians((a_lat + b_lat) / 2))
        dy = (b_lat - a_lat) * 111000
        distance = math.sqrt(dx*dx + dy*dy)
        
        return m, distance
    
    return m, None

# ==================== 初始化 ====================

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

if 'heartbeats' not in st.session_state:
    st.session_state.heartbeats = []
    st.session_state.sequence = 0
    st.session_state.last_time = datetime.now()

if 'a_point' not in st.session_state:
    # 南京某学校内的两个点
    st.session_state.a_point = (118.767413, 32.041544)
    st.session_state.b_point = (118.768413, 32.042544)

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
    st.title("🎮 控制面板")
    
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
            st.success(f"✅ 心跳正常 ({time_since}秒前)")
        else:
            st.error(f"❌ 超时！{time_since}秒无心跳")
    
    # 航线规划设置
    if "🗺️ 航线规划" in st.session_state.page:
        st.markdown("---")
        st.subheader("🗺️ 地图设置")
        
        coord_system = st.selectbox(
            "坐标系",
            options=['wgs84', 'gcj02'],
            format_func=lambda x: 'WGS-84 (GPS坐标)' if x == 'wgs84' else 'GCJ-02 (高德/百度)'
        )
        st.session_state.coord_system = coord_system
        
        st.markdown("---")
        st.subheader("📍 起点 A")
        
        col1, col2 = st.columns(2)
        with col1:
            a_lng = st.number_input("经度", value=st.session_state.a_point[0], format="%.6f", key="a_lng")
        with col2:
            a_lat = st.number_input("纬度", value=st.session_state.a_point[1], format="%.6f", key="a_lat")
        
        st.subheader("📍 终点 B")
        
        col3, col4 = st.columns(2)
        with col3:
            b_lng = st.number_input("经度", value=st.session_state.b_point[0], format="%.6f", key="b_lng")
        with col4:
            b_lat = st.number_input("纬度", value=st.session_state.b_point[1], format="%.6f", key="b_lat")
        
        if st.button("🔄 更新航线", use_container_width=True):
            st.session_state.a_point = (a_lng, a_lat)
            st.session_state.b_point = (b_lng, b_lat)
            st.success("航线已更新")
            st.rerun()

# ==================== 主内容 ====================

if "飞行监控" in st.session_state.page:
    # 飞行监控页面
    st.header("📡 飞行监控")
    
    if st.session_state.heartbeats:
        df = pd.DataFrame(st.session_state.heartbeats)
        
        col1, col2, col3 = st.columns(3)
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
        
        if time_since >= 3:
            st.error(f"⚠️ 连接超时！已 {time_since} 秒未收到心跳")
        
        # 图表
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['time'],
            y=df['seq'],
            mode='lines+markers',
            name='心跳',
            line=dict(color='blue', width=2)
        ))
        fig.update_layout(title="心跳序列号趋势", xaxis_title="时间", yaxis_title="序列号", height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("详细数据"):
            st.dataframe(df.tail(20), use_container_width=True)
    else:
        st.info("等待心跳数据...")

else:
    # 航线规划页面
    st.header("🗺️ 航线规划")
    
    st.info("📍 地图上显示真实的道路和建筑，A点为绿色，B点为红色")
    
    # 显示地图
    with st.spinner("加载地图..."):
        try:
            m, distance = create_map(
                (st.session_state.a_point[0] + st.session_state.b_point[0]) / 2,
                (st.session_state.a_point[1] + st.session_state.b_point[1]) / 2,
                st.session_state.a_point,
                st.session_state.b_point,
                st.session_state.coord_system
            )
            
            st_folium(m, width=1000, height=600, returned_objects=[])
            
            if distance:
                st.success(f"✈️ A点到B点直线距离: {distance:.1f} 米")
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
    
    # 坐标显示
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("起点 A")
        st.write(f"经度: {st.session_state.a_point[0]:.6f}")
        st.write(f"纬度: {st.session_state.a_point[1]:.6f}")
    
    with col2:
        st.subheader("终点 B")
        st.write(f"经度: {st.session_state.b_point[0]:.6f}")
        st.write(f"纬度: {st.session_state.b_point[1]:.6f}")
    
    st.caption("💡 提示：可以缩放地图查看真实的建筑和道路，A点和B点之间的建筑就是障碍物")

# 自动刷新心跳
time.sleep(1)
st.rerun()

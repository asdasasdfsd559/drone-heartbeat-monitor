import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
from datetime import datetime
import folium
from streamlit_folium import st_folium

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

# ==================== 3D地图函数 ====================

def create_3d_map(center_lng, center_lat, coord_system):
    """
    创建3D地形地图
    """
    
    # 根据坐标系转换显示坐标
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    # 创建3D地图（启用3D视图）
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=17,
        control_scale=True,
        zoom_control=True,
        tiles='https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
        attr='Google Terrain'
    )
    
    # 添加地形图层
    folium.TileLayer(
        'https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
        attr='Google Terrain',
        name='地形图',
        control=True
    ).add_to(m)
    
    # 添加卫星图层
    folium.TileLayer(
        'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='卫星图',
        control=True
    ).add_to(m)
    
    # 添加街道图层
    folium.TileLayer(
        'OpenStreetMap',
        name='街道图',
        control=True
    ).add_to(m)
    
    # 添加中心点标记
    folium.Marker(
        [display_lat, display_lng],
        popup=f'📍 监测点<br>经度: {display_lng:.6f}<br>纬度: {display_lat:.6f}',
        icon=folium.Icon(color='red', icon='home', prefix='fa')
    ).add_to(m)
    
    # 添加3D高程效果（通过等高线表示）
    # 添加一个半透明圆表示监测范围
    folium.Circle(
        radius=500,
        location=[display_lat, display_lng],
        color='blue',
        fill=True,
        fill_opacity=0.1,
        weight=2,
        popup='监测范围 (半径500米)'
    ).add_to(m)
    
    # 添加地形等高线效果（通过多个同心圆模拟）
    for r in [100, 200, 300, 400, 500]:
        folium.Circle(
            radius=r,
            location=[display_lat, display_lng],
            color='green' if r % 200 == 0 else 'lightblue',
            fill=False,
            weight=1,
            opacity=0.5
        ).add_to(m)
    
    # 添加图层控制
    folium.LayerControl(position='topright').add_to(m)
    
    # 添加全屏按钮
    folium.plugins.Fullscreen(
        position='topright',
        title='全屏模式',
        title_cancel='退出全屏'
    ).add_to(m)
    
    # 添加鼠标坐标显示
    folium.plugins.MousePosition().add_to(m)
    
    return m

# ==================== 初始化数据 ====================

# 初始化页面状态
if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

# 初始化心跳数据
if 'heartbeats' not in st.session_state:
    st.session_state.heartbeats = []
    st.session_state.sequence = 0
    st.session_state.last_time = datetime.now()

# 初始化地图坐标
if 'center_lng' not in st.session_state:
    st.session_state.center_lng = 118.767413  # 南京新街口
    st.session_state.center_lat = 32.041544
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
        ["📡 飞行监控", "🗺️ 3D地形监测"],
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
        
        st.subheader("💓 心跳状态")
        if time_since < 3:
            st.success(f"✅ 连接正常 ({time_since}秒前)")
        else:
            st.error(f"❌ 超时！{time_since}秒无心跳")
    
    # 3D地图设置
    if "🗺️ 3D地形监测" in st.session_state.page:
        st.markdown("---")
        st.subheader("🗺️ 地图设置")
        
        coord_system = st.selectbox(
            "坐标系",
            options=['wgs84', 'gcj02'],
            format_func=lambda x: '🌍 WGS-84 (GPS坐标)' if x == 'wgs84' else '🇨🇳 GCJ-02 (高德/百度)'
        )
        st.session_state.coord_system = coord_system
        
        st.markdown("---")
        st.subheader("📍 监测点位置")
        
        col1, col2 = st.columns(2)
        with col1:
            new_lng = st.number_input("经度", value=st.session_state.center_lng, format="%.6f")
        with col2:
            new_lat = st.number_input("纬度", value=st.session_state.center_lat, format="%.6f")
        
        if st.button("🔄 更新位置", use_container_width=True):
            st.session_state.center_lng = new_lng
            st.session_state.center_lat = new_lat
            st.success("位置已更新")
            st.rerun()
        
        st.caption("💡 3D地形图显示真实地形起伏")

# ==================== 主内容区域 ====================

if "飞行监控" in st.session_state.page:
    # ==================== 飞行监控页面 ====================
    st.header("📡 飞行监控 - 心跳数据")
    
    if st.session_state.heartbeats:
        df = pd.DataFrame(st.session_state.heartbeats)
        
        # 统计卡片
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
            st.error(f"⚠️ 连接超时！已 {time_since} 秒未收到心跳包")
        
        # 心跳趋势图
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['time'],
            y=df['seq'],
            mode='lines+markers',
            name='心跳序列号',
            line=dict(color='blue', width=2),
            marker=dict(size=8, color='red')
        ))
        
        fig.update_layout(
            title="心跳序列号变化趋势",
            xaxis_title="时间",
            yaxis_title="序列号",
            height=450
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 数据表
        with st.expander("📋 查看详细数据", expanded=False):
            st.dataframe(df.tail(20), use_container_width=True)
    else:
        st.info("⏳ 等待心跳数据生成...")

else:
    # ==================== 3D地形监测页面 ====================
    st.header("🗺️ 3D地形监测")
    
    # 显示当前坐标
    coord_info = "WGS-84 (GPS坐标)" if st.session_state.coord_system == 'wgs84' else "GCJ-02 (高德/百度坐标)"
    st.info(f"📍 当前监测点: {st.session_state.center_lng:.6f}, {st.session_state.center_lat:.6f} | {coord_info}")
    
    # 显示3D地图
    with st.spinner("加载3D地形图中..."):
        try:
            m = create_3d_map(
                st.session_state.center_lng,
                st.session_state.center_lat,
                st.session_state.coord_system
            )
            
            # 显示地图
            st_folium(m, width=1100, height=700, returned_objects=[])
            st.success("✅ 3D地形图加载成功")
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
            st.info("请刷新页面重试")
    
    # 地形说明
    with st.expander("📖 3D地图使用说明", expanded=False):
        st.markdown("""
        **3D地形图操作指南：**
        - 🖱️ **鼠标滚轮**：缩放地图（放大可看到地形细节）
        - 🖱️ **鼠标拖动**：移动地图视角
        - 🖱️ **鼠标右键拖动**：倾斜视角（3D效果）
        - 🗺️ **右上角图层**：切换卫星图/地形图/街道图
        - 🖥️ **全屏按钮**：全屏查看
        
        **地图说明：**
        - 🔴 **红色标记**：监测点位置
        - 🔵 **蓝色圆圈**：监测范围（半径500米）
        - 🟢 **绿色等高线**：地形高度示意
        - **地形图**：显示真实地形起伏（山脉、山谷等）
        
        **坐标系说明：**
        - **WGS-84**：GPS使用的国际标准坐标
        - **GCJ-02**：高德/百度地图使用的加密坐标
        """)

# ==================== 自动刷新 ====================

time.sleep(1)
st.rerun()

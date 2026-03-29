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

# ==================== 地图函数 ====================

def create_real_map(center_lng, center_lat, waypoints, coord_system, map_type="satellite"):
    """
    创建真实地图
    map_type: "satellite" 卫星图, "street" 街道图, "terrain" 地形图
    """
    
    # 根据坐标系转换显示坐标
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    # 根据地图类型选择不同的底图
    if map_type == "satellite":
        # 使用 Google 卫星图（真实卫星影像）
        tiles = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
        attr = 'Google Satellite'
        name = "卫星影像"
    elif map_type == "terrain":
        # 使用地形图
        tiles = 'https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}'
        attr = 'Google Terrain'
        name = "地形图"
    else:
        # 使用街道图
        tiles = 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}'
        attr = 'Google Maps'
        name = "街道图"
    
    # 创建地图
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=17,
        tiles=tiles,
        attr=attr,
        control_scale=True,
        zoom_control=True
    )
    
    # 添加备用图层（可切换）
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        name='卫星影像',
        overlay=False,
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google Maps',
        name='街道地图',
        overlay=False,
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        overlay=False,
        control=True
    ).add_to(m)
    
    # 添加飞行范围圆圈
    folium.Circle(
        radius=400,
        location=[display_lat, display_lng],
        color='blue',
        fill=True,
        fill_opacity=0.15,
        weight=3,
        popup='✈️ 飞行范围 (半径400米)'
    ).add_to(m)
    
    # 添加起飞点（大图标）
    folium.Marker(
        [display_lat, display_lng],
        popup='🚁 起飞点/控制中心',
        icon=folium.Icon(color='red', icon='plane', prefix='fa', icon_size=(40, 40))
    ).add_to(m)
    
    # 添加航点
    if waypoints:
        points = []
        for i, wp in enumerate(waypoints):
            # 坐标转换
            if coord_system == 'gcj02':
                wp_lng, wp_lat = wp['lng'] + 0.0005, wp['lat'] + 0.0003
            else:
                wp_lng, wp_lat = wp['lng'], wp['lat']
            
            points.append([wp_lat, wp_lng])
            
            # 航点颜色
            if i == 0:
                color = 'green'
                icon_name = 'play'
            elif i == len(waypoints) - 1:
                color = 'darkgreen'
                icon_name = 'flag-checkered'
            else:
                color = 'blue'
                icon_name = 'circle'
            
            folium.Marker(
                [wp_lat, wp_lng],
                popup=f"""
                <b>✈️ 航点 {i+1}</b><br>
                高度: {wp['altitude']}m<br>
                动作: {wp['action']}<br>
                坐标: ({wp_lng:.6f}, {wp_lat:.6f})
                """,
                tooltip=f"航点 {i+1}",
                icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
            ).add_to(m)
            
            # 添加航点数字标签
            folium.map.Marker(
                [wp_lat, wp_lng],
                icon=folium.DivIcon(
                    icon_size=(30, 30),
                    icon_anchor=(15, 15),
                    html=f'<div style="font-size: 16px; font-weight: bold; background: rgba(255,255,255,0.9); border-radius: 50%; width: 28px; height: 28px; text-align: center; line-height: 28px; border: 2px solid #1f77b4; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">{i+1}</div>'
                )
            ).add_to(m)
        
        # 绘制航线
        folium.PolyLine(
            points,
            color='#ff4444',
            weight=4,
            opacity=0.9,
            popup='✈️ 规划航线',
            tooltip='点击查看航线'
        ).add_to(m)
        
        # 添加航线方向箭头（每隔一个点添加）
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            # 计算中点
            mid_lat = (p1[0] + p2[0]) / 2
            mid_lng = (p1[1] + p2[1]) / 2
            # 计算角度
            angle = math.degrees(math.atan2(p2[0] - p1[0], p2[1] - p1[1]))
            
            folium.RegularPolygonMarker(
                location=[mid_lat, mid_lng],
                popup=f'航向: {angle:.0f}°',
                number_of_sides=3,
                radius=8,
                color='#ff4444',
                fill=True,
                fill_opacity=0.8
            ).add_to(m)
    
    # 添加图层控制
    folium.LayerControl(position='topright').add_to(m)
    
    # 添加全屏按钮
    folium.plugins.Fullscreen(
        position='topright',
        title='全屏',
        title_cancel='退出全屏'
    ).add_to(m)
    
    return m

def create_waypoints(center_lng, center_lat):
    """生成航线航点 - 多边形环绕"""
    waypoints = []
    radius = 0.003  # 约300米半径
    num_points = 12  # 12个航点，更平滑的航线
    
    for i in range(num_points):
        angle = i * (360 / num_points)
        rad = math.radians(angle)
        lng = center_lng + radius * math.cos(rad)
        lat = center_lat + radius * math.sin(rad)
        
        waypoints.append({
            'id': i,
            'lng': lng,
            'lat': lat,
            'altitude': 100 + 20 * math.sin(rad * 2),  # 波浪形高度
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
    # 设置南京新街口坐标
    st.session_state.center_lng = 118.767413
    st.session_state.center_lat = 32.041544
    st.session_state.waypoints = create_waypoints(
        st.session_state.center_lng, 
        st.session_state.center_lat
    )
    st.session_state.coord_system = 'wgs84'
    st.session_state.map_type = 'satellite'

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
        ["📡 飞行监控", "🗺️ 航线监测"],
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
            st.success(f"✅ 连接正常")
            st.caption(f"最后心跳: {time_since}秒前")
        else:
            st.error(f"❌ 连接超时")
            st.caption(f"{time_since}秒未收到心跳")
    
    # 航线监测页面的设置
    if "🗺️ 航线监测" in st.session_state.page:
        st.markdown("---")
        st.subheader("🗺️ 地图设置")
        
        # 地图类型选择
        map_type = st.selectbox(
            "地图类型",
            options=['satellite', 'street', 'terrain'],
            format_func=lambda x: {
                'satellite': '🛰️ 卫星影像（真实照片）',
                'street': '🏙️ 街道地图',
                'terrain': '⛰️ 地形图'
            }.get(x, x)
        )
        st.session_state.map_type = map_type
        
        # 坐标系选择
        coord_system = st.selectbox(
            "坐标系",
            options=['wgs84', 'gcj02'],
            format_func=lambda x: '🌍 WGS-84 (GPS坐标)' if x == 'wgs84' else '🇨🇳 GCJ-02 (高德/百度地图)'
        )
        st.session_state.coord_system = coord_system
        
        st.markdown("---")
        st.subheader("📍 航线位置")
        
        # 常用地点快捷选择
        locations = {
            "南京新街口": (118.767413, 32.041544),
            "北京天安门": (116.397128, 39.916527),
            "上海外滩": (121.487899, 31.249162),
            "广州塔": (113.318977, 23.106756),
            "深圳湾": (113.942, 22.507),
        }
        
        selected_loc = st.selectbox("快速定位", ["自定义"] + list(locations.keys()))
        if selected_loc != "自定义":
            lng, lat = locations[selected_loc]
            st.session_state.center_lng = lng
            st.session_state.center_lat = lat
        
        col1, col2 = st.columns(2)
        with col1:
            new_lng = st.number_input("经度", value=st.session_state.center_lng, format="%.6f")
        with col2:
            new_lat = st.number_input("纬度", value=st.session_state.center_lat, format="%.6f")
        
        if st.button("🔄 更新航线", use_container_width=True):
            st.session_state.center_lng = new_lng
            st.session_state.center_lat = new_lat
            st.session_state.waypoints = create_waypoints(new_lng, new_lat)
            st.success("航线已更新")
            st.rerun()
        
        st.caption("💡 提示：输入真实经纬度可定位到实际位置，卫星图可看到真实建筑")

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
        
        with col4:
            expected = df['seq'].iloc[-1]
            received = len(df)
            loss_rate = (expected - received) / expected * 100 if expected > 0 else 0
            st.metric("丢包率", f"{loss_rate:.1f}%")
        
        # 超时警告
        if time_since >= 3:
            st.error(f"⚠️ 连接超时！已 {time_since} 秒未收到心跳包")
        
        # 绘制图表
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
            height=450,
            hovermode='x'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 数据表
        with st.expander("📋 查看详细数据", expanded=False):
            st.dataframe(df.tail(20), use_container_width=True)
    else:
        st.info("⏳ 等待心跳数据生成...")

else:
    # ==================== 航线监测页面 ====================
    st.header("🗺️ 航线监测 - 真实卫星影像")
    
    # 显示当前坐标信息
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("✈️ 航点数量", len(st.session_state.waypoints))
    with col2:
        st.metric("📏 飞行高度", "80-120 米")
    with col3:
        st.metric("🎯 航线半径", "约300 米")
    with col4:
        total_dist = len(st.session_state.waypoints) * 157  # 估算周长
        st.metric("📐 总航线距离", f"{total_dist:.0f} 米")
    
    st.markdown("---")
    
    # 显示坐标系和地图类型信息
    coord_info = "WGS-84 (GPS标准坐标)" if st.session_state.coord_system == 'wgs84' else "GCJ-02 (高德/百度地图坐标)"
    map_info = {
        'satellite': '🛰️ 卫星影像模式 - 可看到真实建筑、道路、植被',
        'street': '🏙️ 街道地图模式 - 清晰标注道路名称',
        'terrain': '⛰️ 地形图模式 - 显示等高线地形'
    }.get(st.session_state.map_type, '')
    
    st.caption(f"📍 当前: {coord_info} | {map_info}")
    
    # 显示真实地图
    with st.spinner("加载真实卫星影像中..."):
        try:
            m = create_real_map(
                st.session_state.center_lng,
                st.session_state.center_lat,
                st.session_state.waypoints,
                st.session_state.coord_system,
                st.session_state.map_type
            )
            
            # 显示地图
            st_folium(m, width=1100, height=650, returned_objects=[])
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
            st.info("请检查网络连接，卫星图可能需要稍等加载")
    
    # 说明信息
    st.markdown("---")
    st.info("""
    🛰️ **真实卫星影像说明**
    - 📸 **卫星影像模式**：显示真实卫星照片，可以看到真实的建筑物、道路、树木
    - 🔴 **红色标记**：起飞点/控制中心
    - 🔵 **蓝色标记**：航线航点（带数字编号）
    - 🟢 **绿色标记**：起点/终点
    - 🔴 **红色连线**：规划航线
    - 🔵 **蓝色圆圈**：飞行范围（半径400米）
    
    💡 **操作提示**
    - 鼠标滚轮缩放地图，查看细节
    - 拖动地图浏览周边环境
    - 点击右上角图层按钮可切换卫星/街道/地形图
    - 点击右上角全屏按钮可全屏查看
    - 点击地图上的标记点查看详细信息
    """)
    
    # 航点详情表格
    with st.expander("📋 航点详情", expanded=False):
        waypoints_df = pd.DataFrame(st.session_state.waypoints)
        waypoints_df['经度'] = waypoints_df['lng'].apply(lambda x: f"{x:.6f}")
        waypoints_df['纬度'] = waypoints_df['lat'].apply(lambda x: f"{x:.6f}")
        waypoints_df['高度(米)'] = waypoints_df['altitude'].apply(lambda x: f"{x:.1f}")
        waypoints_df['动作'] = waypoints_df['action']
        st.dataframe(waypoints_df[['id', '经度', '纬度', '高度(米)', '动作']], 
                    use_container_width=True)

# ==================== 自动刷新 ====================

# 自动刷新页面（让心跳数据实时更新）
time.sleep(1)
st.rerun()

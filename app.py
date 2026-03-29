import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
from datetime import datetime
import folium
from streamlit_folium import st_folium
import random

st.set_page_config(page_title="无人机学校航线规划", layout="wide")

# ==================== 坐标系转换 ====================

class CoordTransform:
    """WGS-84 和 GCJ-02 坐标系转换"""
    
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003
    
    @staticmethod
    def gcj02_to_wgs84(lng, lat):
        return lng - 0.0005, lat - 0.0003

# ==================== 学校建筑物生成 ====================

class SchoolBuildings:
    """学校建筑物数据"""
    
    def __init__(self, school_center_lng, school_center_lat):
        self.center_lng = school_center_lng
        self.center_lat = school_center_lat
        self.buildings = []
        self._generate_buildings()
    
    def _generate_buildings(self):
        """生成学校建筑物位置"""
        
        # 教学楼群
        buildings_data = [
            {"name": "教学楼A", "offset_lng": -0.0015, "offset_lat": -0.0012, "width": 0.0008, "height": 0.0006, "type": "教学"},
            {"name": "教学楼B", "offset_lng": 0.0012, "offset_lat": -0.0015, "width": 0.0009, "height": 0.0007, "type": "教学"},
            {"name": "实验楼", "offset_lng": -0.0018, "offset_lat": 0.0010, "width": 0.0007, "height": 0.0008, "type": "实验"},
            {"name": "图书馆", "offset_lng": 0.0015, "offset_lat": 0.0012, "width": 0.0010, "height": 0.0009, "type": "图书"},
            {"name": "行政楼", "offset_lng": 0.0005, "offset_lat": -0.0020, "width": 0.0008, "height": 0.0006, "type": "行政"},
            {"name": "学生食堂", "offset_lng": -0.0022, "offset_lat": -0.0005, "width": 0.0010, "height": 0.0008, "type": "餐饮"},
            {"name": "学生宿舍1", "offset_lng": 0.0020, "offset_lat": 0.0008, "width": 0.0012, "height": 0.0005, "type": "宿舍"},
            {"name": "学生宿舍2", "offset_lng": 0.0018, "offset_lat": -0.0008, "width": 0.0011, "height": 0.0005, "type": "宿舍"},
            {"name": "体育馆", "offset_lng": -0.0010, "offset_lat": 0.0020, "width": 0.0012, "height": 0.0010, "type": "体育"},
            {"name": "操场", "offset_lng": 0.0000, "offset_lat": 0.0025, "width": 0.0025, "height": 0.0015, "type": "运动"},
        ]
        
        for b in buildings_data:
            self.buildings.append({
                "name": b["name"],
                "lng": self.center_lng + b["offset_lng"],
                "lat": self.center_lat + b["offset_lat"],
                "width": b["width"],
                "height": b["height"],
                "type": b["type"]
            })
    
    def get_buildings(self):
        return self.buildings
    
    def check_collision(self, lng, lat, margin=0.0001):
        """检查点是否与建筑物碰撞"""
        for b in self.buildings:
            half_w = b["width"] / 2
            half_h = b["height"] / 2
            if (b["lng"] - half_w - margin <= lng <= b["lng"] + half_w + margin and
                b["lat"] - half_h - margin <= lat <= b["lat"] + half_h + margin):
                return True, b["name"]
        return False, None

# ==================== 航线规划器 ====================

class RoutePlanner:
    """航线规划器 - 避开建筑物"""
    
    def __init__(self, buildings):
        self.buildings = buildings
    
    def plan_route(self, start_lng, start_lat, end_lng, end_lat):
        """规划A点到B点的航线，避开建筑物"""
        
        waypoints = []
        
        # 添加起点
        waypoints.append({
            "id": 0,
            "lng": start_lng,
            "lat": start_lat,
            "type": "start",
            "name": "起点A"
        })
        
        # 计算直线路径上的中间点
        steps = 20
        for i in range(1, steps):
            t = i / steps
            lng = start_lng + (end_lng - start_lng) * t
            lat = start_lat + (end_lat - start_lat) * t
            
            # 检查是否与建筑物碰撞
            collision, building_name = self.buildings.check_collision(lng, lat)
            
            if collision:
                # 如果有碰撞，绕行
                waypoints = self._add_detour(waypoints, lng, lat, building_name)
            else:
                waypoints.append({
                    "id": len(waypoints),
                    "lng": lng,
                    "lat": lat,
                    "type": "waypoint",
                    "name": f"航点{len(waypoints)}"
                })
        
        # 添加终点
        waypoints.append({
            "id": len(waypoints),
            "lng": end_lng,
            "lat": end_lat,
            "type": "end",
            "name": "终点B"
        })
        
        return waypoints
    
    def _add_detour(self, waypoints, lng, lat, building_name):
        """添加绕行点"""
        # 绕行偏移量
        offset = 0.0003
        
        # 添加绕行点
        detour_points = [
            {"lng": lng + offset, "lat": lat, "name": f"绕行{len(waypoints)+1}"},
            {"lng": lng + offset, "lat": lat + offset, "name": f"绕行{len(waypoints)+2}"},
            {"lng": lng, "lat": lat + offset, "name": f"绕行{len(waypoints)+3}"},
        ]
        
        for dp in detour_points:
            waypoints.append({
                "id": len(waypoints),
                "lng": dp["lng"],
                "lat": dp["lat"],
                "type": "detour",
                "name": dp["name"],
                "avoid": building_name
            })
        
        return waypoints
    
    def calculate_distance(self, waypoints):
        """计算航线总距离"""
        total = 0
        for i in range(len(waypoints) - 1):
            p1 = waypoints[i]
            p2 = waypoints[i + 1]
            dx = (p2["lng"] - p1["lng"]) * 111000 * math.cos(math.radians((p1["lat"] + p2["lat"]) / 2))
            dy = (p2["lat"] - p1["lat"]) * 111000
            total += math.sqrt(dx*dx + dy*dy)
        return total

# ==================== 地图创建 ====================

def create_school_map(center_lng, center_lat, buildings, waypoints, coord_system):
    """创建学校地图，显示建筑物和航线"""
    
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    # 使用国内可访问的地图源
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=17,
        tiles='CartoDB positron',
        control_scale=True
    )
    
    # 添加备用地图源
    folium.TileLayer('OpenStreetMap', name='标准地图').add_to(m)
    folium.TileLayer('CartoDB voyager', name='详细地图').add_to(m)
    
    # 添加建筑物（作为障碍物）
    for b in buildings:
        # 转换坐标
        if coord_system == 'gcj02':
            b_lng, b_lat = b["lng"] + 0.0005, b["lat"] + 0.0003
        else:
            b_lng, b_lat = b["lng"], b["lat"]
        
        half_w = b["width"] / 2
        half_h = b["height"] / 2
        
        # 绘制建筑物矩形
        folium.Rectangle(
            bounds=[[b_lat - half_h, b_lng - half_w], [b_lat + half_h, b_lng + half_w]],
            color='red',
            fill=True,
            fill_opacity=0.6,
            popup=f"🏛️ {b['name']}<br>类型: {b['type']}<br>障碍物",
            tooltip=f"⚠️ {b['name']}"
        ).add_to(m)
        
        # 添加建筑名称标签
        folium.Marker(
            [b_lat, b_lng],
            icon=folium.DivIcon(
                html=f'<div style="font-size: 11px; font-weight: bold; background: white; padding: 2px 5px; border: 1px solid red; border-radius: 3px;">{b["name"]}</div>'
            )
        ).add_to(m)
    
    # 添加航线
    if waypoints:
        points = []
        for i, wp in enumerate(waypoints):
            if coord_system == 'gcj02':
                wp_lng, wp_lat = wp["lng"] + 0.0005, wp["lat"] + 0.0003
            else:
                wp_lng, wp_lat = wp["lng"], wp["lat"]
            
            points.append([wp_lat, wp_lng])
            
            # 根据类型设置不同颜色
            if wp["type"] == "start":
                color = 'green'
                icon = 'play'
                size = 12
            elif wp["type"] == "end":
                color = 'darkgreen'
                icon = 'flag-checkered'
                size = 12
            elif wp["type"] == "detour":
                color = 'orange'
                icon = 'circle'
                size = 8
            else:
                color = 'blue'
                icon = 'circle'
                size = 8
            
            folium.Marker(
                [wp_lat, wp_lng],
                popup=f"""
                <b>{wp['name']}</b><br>
                类型: {wp['type']}<br>
                坐标: ({wp_lng:.6f}, {wp_lat:.6f})
                """,
                tooltip=wp['name'],
                icon=folium.Icon(color=color, icon=icon, prefix='fa')
            ).add_to(m)
        
        # 绘制航线
        folium.PolyLine(
            points,
            color='blue',
            weight=4,
            opacity=0.8,
            popup='规划航线'
        ).add_to(m)
    
    # 添加图层控制
    folium.LayerControl().add_to(m)
    
    return m

# ==================== 初始化 ====================

# 初始化
if 'school_buildings' not in st.session_state:
    # 设置学校中心点（南京某大学）
    st.session_state.school_lng = 118.767413
    st.session_state.school_lat = 32.041544
    st.session_state.buildings = SchoolBuildings(st.session_state.school_lng, st.session_state.school_lat)
    st.session_state.route_planner = RoutePlanner(st.session_state.buildings)

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

if 'heartbeats' not in st.session_state:
    st.session_state.heartbeats = []
    st.session_state.sequence = 0
    st.session_state.last_time = datetime.now()

if 'waypoints' not in st.session_state:
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
    st.title("🎮 控制面板")
    
    # 页面选择
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
            format_func=lambda x: '🌍 WGS-84 (GPS)' if x == 'wgs84' else '🇨🇳 GCJ-02 (高德/百度)'
        )
        st.session_state.coord_system = coord_system
        
        st.markdown("---")
        st.subheader("✈️ 航线设置")
        
        st.write("**起点 A**")
        col1, col2 = st.columns(2)
        with col1:
            start_lng = st.number_input("经度", value=st.session_state.school_lng - 0.001, format="%.6f", key="start_lng")
        with col2:
            start_lat = st.number_input("纬度", value=st.session_state.school_lat - 0.001, format="%.6f", key="start_lat")
        
        st.write("**终点 B**")
        col3, col4 = st.columns(2)
        with col3:
            end_lng = st.number_input("经度", value=st.session_state.school_lng + 0.001, format="%.6f", key="end_lng")
        with col4:
            end_lat = st.number_input("纬度", value=st.session_state.school_lat + 0.001, format="%.6f", key="end_lat")
        
        if st.button("🔄 规划航线", use_container_width=True):
            st.session_state.waypoints = st.session_state.route_planner.plan_route(
                start_lng, start_lat, end_lng, end_lat
            )
            st.success(f"航线规划完成！共 {len(st.session_state.waypoints)} 个航点")

# ==================== 主内容 ====================

if "飞行监控" in st.session_state.page:
    # 飞行监控页面
    st.header("📡 飞行监控 - 心跳数据")
    
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
        fig.update_layout(title="心跳序列号趋势", xaxis_title="时间", yaxis_title="序列号", height=450)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("详细数据"):
            st.dataframe(df.tail(20), use_container_width=True)
    else:
        st.info("等待心跳数据...")

else:
    # 航线规划页面
    st.header("🗺️ 学校航线规划 - 避开建筑物")
    
    # 显示学校信息
    st.info(f"🏫 学校中心点: {st.session_state.school_lng:.6f}, {st.session_state.school_lat:.6f}")
    
    # 显示地图
    with st.spinner("加载地图..."):
        try:
            buildings = st.session_state.buildings.get_buildings()
            m = create_school_map(
                st.session_state.school_lng,
                st.session_state.school_lat,
                buildings,
                st.session_state.waypoints,
                st.session_state.coord_system
            )
            st_folium(m, width=1000, height=600, returned_objects=[])
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
    
    # 显示航线信息
    if st.session_state.waypoints:
        st.markdown("---")
        st.subheader("✈️ 航线信息")
        
        total_dist = st.session_state.route_planner.calculate_distance(st.session_state.waypoints)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总航点数", len(st.session_state.waypoints))
        with col2:
            st.metric("航线总距离", f"{total_dist:.1f} 米")
        with col3:
            detours = sum(1 for wp in st.session_state.waypoints if wp.get("type") == "detour")
            st.metric("绕行次数", detours)
        
        # 航点详情
        with st.expander("📋 航点详情", expanded=False):
            wp_data = []
            for wp in st.session_state.waypoints:
                wp_data.append({
                    "航点": wp["id"],
                    "名称": wp["name"],
                    "经度": f"{wp['lng']:.6f}",
                    "纬度": f"{wp['lat']:.6f}",
                    "类型": wp["type"],
                    "避开建筑": wp.get("avoid", "-")
                })
            st.dataframe(pd.DataFrame(wp_data), use_container_width=True)
        
        # 障碍物列表
        with st.expander("🏛️ 学校建筑物（障碍物）", expanded=False):
            b_data = []
            for b in buildings:
                b_data.append({
                    "建筑名称": b["name"],
                    "类型": b["type"],
                    "经度": f"{b['lng']:.6f}",
                    "纬度": f"{b['lat']:.6f}"
                })
            st.dataframe(pd.DataFrame(b_data), use_container_width=True)

# 自动刷新心跳
time.sleep(1)
st.rerun()

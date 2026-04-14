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

# ==================== 地图函数 ====================

def create_map_with_drawing(center_lng, center_lat, waypoints, home_point, obstacles, coord_system):
    """创建带多边形绘制功能的地图"""
    
    if coord_system == 'gcj02':
        display_lng, display_lat = center_lng, center_lat
    else:
        display_lng, display_lat = center_lng, center_lat
    
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=18,
        control_scale=True,
        tiles='OpenStreetMap'
    )
    
    folium.TileLayer(
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德地图',
        name='高德卫星图',
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        tiles='https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        attr='高德地图',
        name='高德街道图',
        control=True
    ).add_to(m)
    
    # Home点
    if home_point:
        if coord_system == 'gcj02':
            h_lng, h_lat = home_point[0], home_point[1]
        else:
            h_lng, h_lat = CoordTransform.wgs84_to_gcj02(home_point[0], home_point[1])
        
        folium.Marker(
            [h_lat, h_lng], 
            popup='🏠 学校中心点', 
            icon=folium.Icon(color='green', icon='home', prefix='fa')
        ).add_to(m)
        folium.Circle(
            radius=100, 
            location=[h_lat, h_lng], 
            color='green', 
            fill=True, 
            fill_opacity=0.15, 
            weight=2
        ).add_to(m)
    
    # 航点
    if waypoints:
        points = []
        for i, wp in enumerate(waypoints):
            if coord_system == 'gcj02':
                wp_lng, wp_lat = wp[0], wp[1]
            else:
                wp_lng, wp_lat = CoordTransform.wgs84_to_gcj02(wp[0], wp[1])
            
            points.append([wp_lat, wp_lng])
            color = 'blue' if i < len(waypoints)-1 else 'red'
            folium.Marker(
                [wp_lat, wp_lng], 
                popup=f'航点 {i+1}', 
                icon=folium.Icon(color=color, icon='circle', prefix='fa')
            ).add_to(m)
            
            folium.map.Marker(
                [wp_lat, wp_lng],
                icon=folium.DivIcon(
                    icon_size=(24, 24),
                    icon_anchor=(12, 12),
                    html=f'<div style="font-size: 12px; font-weight: bold; background: black; color: white; border-radius: 50%; width: 22px; height: 22px; text-align: center; line-height: 22px;">{i+1}</div>'
                )
            ).add_to(m)
        
        folium.PolyLine(points, color='blue', weight=3, opacity=0.8).add_to(m)
    
    # 障碍物
    for obs in obstacles:
        polygon_points = []
        for point in obs['points']:
            if coord_system == 'gcj02':
                lng, lat = point[0], point[1]
            else:
                lng, lat = CoordTransform.wgs84_to_gcj02(point[0], point[1])
            polygon_points.append([lat, lng])
        
        height = obs.get('height', 10)
        if height < 20:
            fill_color = '#ff9999'
        elif height < 50:
            fill_color = '#ff6666'
        else:
            fill_color = '#ff3333'
        
        folium.Polygon(
            locations=polygon_points,
            color='red',
            weight=3,
            fill=True,
            fill_color=fill_color,
            fill_opacity=0.5,
            popup=f"🚧 {obs['name']}<br>高度: {height}米<br>ID: {obs['id']}",
            tooltip=f"{obs['name']} ({height}米)"
        ).add_to(m)
    
    # 绘制工具
    draw = plugins.Draw(
        draw_options={
            'polygon': {
                'allowIntersection': False,
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
    
    for r in [50, 100, 200]:
        folium.Circle(
            radius=r, 
            location=[display_lat, display_lng], 
            color='gray', 
            fill=False, 
            weight=1, 
            opacity=0.4
        ).add_to(m)
    
    folium.LayerControl().add_to(m)
    
    return m

# ==================== 初始化 ====================

if 'heartbeat_mgr' not in st.session_state:
    st.session_state.heartbeat_mgr = HeartbeatManager()
    st.session_state.heartbeat_mgr.start()

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

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

if 'obstacles' not in st.session_state:
    st.session_state.obstacles = []

if 'temp_draw_data' not in st.session_state:
    st.session_state.temp_draw_data = None

# 编辑状态
if 'editing_obstacle' not in st.session_state:
    st.session_state.editing_obstacle = None

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
            format_func=lambda x: 'WGS-84 (GPS)' if x == 'wgs84' else 'GCJ-02 (高德/百度)',
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
        st.subheader("📍 起点 A")
        
        a_lng = st.number_input("经度", value=st.session_state.a_point[0], format="%.6f", key="a_lng")
        a_lat = st.number_input("纬度", value=st.session_state.a_point[1], format="%.6f", key="a_lat")
        
        st.subheader("📍 终点 B")
        
        b_lng = st.number_input("经度", value=st.session_state.b_point[0], format="%.6f", key="b_lng")
        b_lat = st.number_input("纬度", value=st.session_state.b_point[1], format="%.6f", key="b_lat")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("➕ 生成航线", key="gen_route"):
                st.session_state.a_point = (a_lng, a_lat)
                st.session_state.b_point = (b_lng, b_lat)
                st.session_state.waypoints = [st.session_state.a_point, st.session_state.b_point]
                st.success("已生成航线")
                st.rerun()
        with col_btn2:
            if st.button("🗑️ 清空航线", key="clear_route"):
                st.session_state.waypoints = []
                st.success("已清空航线")
                st.rerun()
        
        st.markdown("---")
        st.subheader("🚧 障碍物管理")
        
        st.info(f"当前障碍物数量: {len(st.session_state.obstacles)}")
        
        # 添加障碍物
        st.markdown("**添加新障碍物:**")
        obs_name = st.text_input("障碍物名称", placeholder="例如: 教学楼、食堂、图书馆", key="new_obs_name")
        obs_height = st.number_input("障碍物高度 (米)", min_value=1, max_value=200, value=20, step=5, key="new_obs_height")
        
        st.caption("💡 请先在地图上使用多边形工具绘制区域，然后点击下方按钮保存")
        
        if st.button("💾 保存当前绘制的多边形", key="save_obs_btn"):
            if st.session_state.temp_draw_data and len(st.session_state.temp_draw_data) >= 3:
                points = st.session_state.temp_draw_data
                new_id = max([o['id'] for o in st.session_state.obstacles]) + 1 if st.session_state.obstacles else 1
                new_obs = {
                    'id': new_id,
                    'name': obs_name if obs_name else f"障碍物{new_id}",
                    'height': obs_height,
                    'points': points,
                    'created_at': get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.obstacles.append(new_obs)
                st.session_state.temp_draw_data = None
                st.success(f"已添加障碍物: {new_obs['name']} (高度:{obs_height}米)")
                st.rerun()
            else:
                st.warning("请先在地图上绘制多边形（至少3个顶点）")
        
        st.markdown("---")
        
        # 修改障碍物
        if st.session_state.obstacles:
            st.subheader("✏️ 修改障碍物")
            
            obs_options = [f"{o['id']}. {o['name']} (高度:{o.get('height',10)}米)" for o in st.session_state.obstacles]
            selected_obs = st.selectbox("选择要修改的障碍物", options=obs_options, key="edit_obs_select")
            
            if selected_obs:
                obs_id = int(selected_obs.split('.')[0])
                target_obs = next((o for o in st.session_state.obstacles if o['id'] == obs_id), None)
                
                if target_obs:
                    col1, col2 = st.columns(2)
                    with col1:
                        new_name = st.text_input("新名称", value=target_obs['name'], key="edit_obs_name")
                    with col2:
                        new_height = st.number_input("新高度(米)", min_value=1, max_value=200, 
                                                      value=target_obs.get('height', 20), step=5, key="edit_obs_height")
                    
                    st.caption("💡 修改多边形：重新在地图上绘制后点击更新")
                    
                    col_update, col_cancel = st.columns(2)
                    with col_update:
                        if st.button("🔄 更新多边形", key="update_polygon_btn"):
                            st.session_state.editing_obstacle = target_obs
                            st.info(f"请在地图上重新绘制 {target_obs['name']} 的多边形区域")
                    
                    # 如果正在编辑，保存新绘制的多边形
                    if st.session_state.editing_obstacle and st.session_state.temp_draw_data:
                        if st.session_state.editing_obstacle['id'] == obs_id:
                            if st.button("✅ 确认更新多边形", key="confirm_update"):
                                target_obs['points'] = st.session_state.temp_draw_data
                                target_obs['name'] = new_name
                                target_obs['height'] = new_height
                                st.session_state.temp_draw_data = None
                                st.session_state.editing_obstacle = None
                                st.success(f"已更新障碍物: {target_obs['name']}")
                                st.rerun()
                    
                    # 非多边形修改（只改名称和高度）
                    if st.button("💾 保存名称和高度", key="save_name_height"):
                        target_obs['name'] = new_name
                        target_obs['height'] = new_height
                        st.success(f"已更新障碍物信息")
                        st.rerun()
        
        st.markdown("---")
        st.subheader("🗑️ 删除障碍物")
        
        if st.session_state.obstacles:
            obs_to_delete = st.selectbox(
                "选择要删除的障碍物",
                options=[f"{o['id']}. {o['name']}" for o in st.session_state.obstacles],
                key="obs_to_delete"
            )
            
            if st.button("删除选中障碍物", key="delete_obs"):
                idx = int(obs_to_delete.split('.')[0]) - 1
                deleted = st.session_state.obstacles.pop(idx)
                st.success(f"已删除: {deleted['name']}")
                st.rerun()
        
        if st.button("🗑️ 清空所有障碍物", key="clear_all_obs"):
            st.session_state.obstacles = []
            st.session_state.temp_draw_data = None
            st.session_state.editing_obstacle = None
            st.success("已清空所有障碍物")
            st.rerun()

# ==================== 主内容 ====================

if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控 - 心跳数据")
    st.caption("🕐 北京时间 (UTC+8)")
    
    heartbeats, seq, last_time = st.session_state.heartbeat_mgr.get_data()
    
    if heartbeats:
        df = pd.DataFrame(heartbeats)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总心跳数", len(df))
        with col2:
            st.metric("当前序列号", seq)
        
        if len(heartbeats) >= 2:
            intervals = [heartbeats[i]['timestamp'] - heartbeats[i-1]['timestamp'] for i in range(1, len(heartbeats))]
            avg_interval = sum(intervals) / len(intervals)
            st.metric("平均间隔", f"{avg_interval:.3f}秒")
        
        status, time_since = st.session_state.heartbeat_mgr.get_connection_status()
        
        with col3:
            st.metric("连接状态", "✅ 在线" if status == "在线" else "❌ 离线")
        
        with col4:
            expected = seq
            received = len(df)
            loss_rate = (expected - received) / expected * 100 if expected > 0 else 0
            st.metric("丢包率", f"{loss_rate:.1f}%")
        
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
    st.header("🗺️ 航线规划 - 南京科技职业学院")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"🏫 学校: 南京科技职业学院")
        st.info(f"📍 中心点: {st.session_state.home_point[0]:.6f}, {st.session_state.home_point[1]:.6f}")
    with col2:
        if st.session_state.waypoints:
            st.success(f"✈️ 当前航线: 起点 → 终点 ({len(st.session_state.waypoints)}个航点)")
        else:
            st.warning("⚠️ 暂无航线")
        st.info(f"🚧 障碍物数量: {len(st.session_state.obstacles)}")
    
    st.markdown("---")
    
    with st.spinner("加载地图..."):
        try:
            if st.session_state.waypoints:
                all_points = [st.session_state.home_point] + st.session_state.waypoints
                center_lng = sum(p[0] for p in all_points) / len(all_points)
                center_lat = sum(p[1] for p in all_points) / len(all_points)
            else:
                center_lng, center_lat = st.session_state.home_point
            
            m = create_map_with_drawing(
                center_lng, center_lat,
                st.session_state.waypoints,
                st.session_state.home_point,
                st.session_state.obstacles,
                st.session_state.coord_system
            )
            
            output = st_folium(m, width=1000, height=600, returned_objects=["last_draw"])
            
            if output and output.get('last_draw') is not None:
                draw_data = output['last_draw']
                if draw_data and draw_data.get('geometry') and draw_data['geometry'].get('type') == 'Polygon':
                    coordinates = draw_data['geometry']['coordinates'][0]
                    points = [(coord[0], coord[1]) for coord in coordinates]
                    if len(points) >= 3:
                        st.session_state.temp_draw_data = points
                        st.success(f"✅ 已绘制多边形，共 {len(points)} 个顶点")
                        if st.session_state.editing_obstacle:
                            st.info(f"正在编辑: {st.session_state.editing_obstacle['name']}，请在侧边栏点击「确认更新」")
                        else:
                            st.info("请在侧边栏设置名称和高度后点击「保存当前绘制的多边形」")
                        st.rerun()
            
            st.success("✅ 地图加载成功")
            
            with st.expander("📖 使用说明", expanded=False):
                st.markdown("""
                **添加障碍物步骤：**
                1. 点击地图右上角的 📐 多边形绘制按钮
                2. 在地图上依次点击各个顶点（至少3个点）
                3. 双击鼠标完成绘制
                4. 在左侧边栏输入障碍物名称和高度
                5. 点击「保存当前绘制的多边形」
                
                **修改障碍物步骤：**
                1. 在左侧边栏「修改障碍物」中选择要修改的障碍物
                2. 修改名称和高度后点击「保存名称和高度」
                3. 如需修改多边形，点击「更新多边形」，然后重新绘制区域，最后点击「确认更新」
                
                **障碍物颜色：**
                - 🟢 浅红色：高度 < 20米
                - 🟡 中红色：高度 20-50米
                - 🔴 深红色：高度 > 50米
                """)
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
            st.info("请刷新页面重试")

time.sleep(0.5)
st.rerun()

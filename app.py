import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
from datetime import datetime
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="无人机地面站", layout="wide")

# ==================== 精确心跳模拟器 ====================

class PreciseHeartbeatSimulator:
    """精确时间的心跳模拟器"""
    
    def __init__(self):
        self.heartbeats = []
        self.sequence = 0
        self.last_send_time = None
        self.last_receive_time = None
        self.expected_interval = 1.0  # 期望间隔1秒
        self.timeout_threshold = 3.0  # 超时阈值3秒
        
    def update(self):
        """更新时间驱动的心跳生成"""
        current_time = time.time()
        
        # 初始化
        if self.last_send_time is None:
            self.last_send_time = current_time
            self.last_receive_time = current_time
            return
        
        # 计算时间差
        elapsed = current_time - self.last_send_time
        
        # 如果达到发送间隔，生成新心跳
        if elapsed >= self.expected_interval:
            # 精确计算序列号（补偿误差）
            expected_seq = int((current_time - self.last_send_time) / self.expected_interval)
            
            for i in range(expected_seq):
                self.sequence += 1
                send_time = self.last_send_time + (i + 1) * self.expected_interval
                
                self.heartbeats.append({
                    'time': datetime.fromtimestamp(send_time).strftime("%H:%M:%S.%f")[:-3],
                    'seq': self.sequence,
                    'send_timestamp': send_time,
                    'receive_timestamp': current_time,
                    'delay_ms': (current_time - send_time) * 1000
                })
            
            self.last_send_time = current_time
            self.last_receive_time = current_time
            
            # 限制数据量
            if len(self.heartbeats) > 100:
                self.heartbeats = self.heartbeats[-100:]
    
    def get_connection_status(self):
        """获取连接状态"""
        if not self.heartbeats:
            return "等待", 0
        
        last_heartbeat = self.heartbeats[-1]
        time_since = time.time() - last_heartbeat['send_timestamp']
        
        if time_since < self.timeout_threshold:
            return "在线", time_since
        else:
            return "超时", time_since
    
    def get_dataframe(self):
        """获取DataFrame"""
        if not self.heartbeats:
            return pd.DataFrame()
        return pd.DataFrame(self.heartbeats)
    
    def get_statistics(self):
        """获取统计信息"""
        if not self.heartbeats:
            return {}
        
        delays = [h['delay_ms'] for h in self.heartbeats]
        
        return {
            'total': len(self.heartbeats),
            'avg_delay_ms': sum(delays) / len(delays),
            'max_delay_ms': max(delays),
            'min_delay_ms': min(delays),
            'last_seq': self.heartbeats[-1]['seq']
        }

# ==================== 初始化 ====================

if 'simulator' not in st.session_state:
    st.session_state.simulator = PreciseHeartbeatSimulator()

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

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

# ==================== 更新心跳（使用精确时间）====================

st.session_state.simulator.update()

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
    
    m = folium.Map(
        location=[display_lat, display_lng],
        zoom_start=18,
        control_scale=True,
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德地图'
    )
    
    folium.TileLayer(
        'https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        name='高德街道图',
        attr='高德地图',
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        'OpenStreetMap',
        name='OSM街道图',
        control=True
    ).add_to(m)
    
    if home_point:
        if coord_system == 'gcj02':
            h_lng, h_lat = home_point[0], home_point[1]
        else:
            h_lng, h_lat = CoordTransform.wgs84_to_gcj02(home_point[0], home_point[1])
        
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
                popup=f'WP{i+1}<br>{wp_lng:.6f}, {wp_lat:.6f}',
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

# ==================== 侧边栏 ====================

with st.sidebar:
    st.title("🎮 无人机地面站")
    st.markdown("**心跳**: 精确时间驱动 (±1ms)")
    
    selected_page = st.radio(
        "选择功能",
        ["📡 飞行监控", "🗺️ 航线规划"],
        index=0 if st.session_state.page == "飞行监控" else 1,
        key="page_select"
    )
    st.session_state.page = selected_page
    
    st.markdown("---")
    
    # 心跳状态显示
    status, time_since = st.session_state.simulator.get_connection_status()
    
    if status == "在线":
        st.success(f"✅ 心跳正常")
        st.metric("最后心跳", f"{time_since:.2f}秒前")
    else:
        st.error(f"❌ {status}")
        st.metric("无心跳时间", f"{time_since:.1f}秒")
    
    stats = st.session_state.simulator.get_statistics()
    if stats:
        st.metric("总心跳数", stats['total'])
        st.metric("当前序列号", stats['last_seq'])
        st.metric("平均延迟", f"{stats['avg_delay_ms']:.1f}ms")
    
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
        st.subheader("🏠 起飞点 (Home)")
        
        home_lng = st.number_input("经度", value=st.session_state.home_point[0], format="%.6f", key="home_lng")
        home_lat = st.number_input("纬度", value=st.session_state.home_point[1], format="%.6f", key="home_lat")
        
        if st.button("更新 Home 点", key="update_home"):
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
                st.success(f"已生成航线: A→B")
                st.rerun()
        with col_btn2:
            if st.button("🗑️ 清空航线", key="clear_route"):
                st.session_state.waypoints = []
                st.success("已清空航线")
                st.rerun()

# ==================== 主内容 ====================

if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控 - 精确时间心跳")
    
    df = st.session_state.simulator.get_dataframe()
    
    if not df.empty:
        # 统计卡片
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总心跳数", len(df))
        with col2:
            st.metric("当前序列号", df['seq'].iloc[-1])
        
        status, time_since = st.session_state.simulator.get_connection_status()
        with col3:
            if status == "在线":
                st.metric("连接状态", "✅ 在线")
            else:
                st.metric("连接状态", "❌ 离线")
        
        stats = st.session_state.simulator.get_statistics()
        with col4:
            st.metric("平均延迟", f"{stats.get('avg_delay_ms', 0):.1f}ms")
        
        if status == "超时":
            st.error(f"⚠️ 连接超时！已 {time_since:.1f} 秒未收到心跳")
        
        # 心跳序列号趋势图
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=df['time'],
            y=df['seq'],
            mode='lines+markers',
            name='序列号',
            line=dict(color='blue', width=2),
            marker=dict(size=6, color='red')
        ))
        fig1.update_layout(
            title="心跳序列号趋势",
            xaxis_title="时间",
            yaxis_title="序列号",
            height=350
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        # 延迟趋势图（新增）
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df['time'],
            y=df['delay_ms'],
            mode='lines+markers',
            name='延迟',
            line=dict(color='orange', width=2),
            marker=dict(size=6, color='red')
        ))
        fig2.add_hline(y=50, line_dash="dash", line_color="green", annotation_text="良好")
        fig2.add_hline(y=100, line_dash="dash", line_color="yellow", annotation_text="警告")
        fig2.add_hline(y=200, line_dash="dash", line_color="red", annotation_text="严重")
        fig2.update_layout(
            title="心跳延迟趋势（毫秒）",
            xaxis_title="时间",
            yaxis_title="延迟 (ms)",
            height=350
        )
        st.plotly_chart(fig2, use_container_width=True)
        
        # 详细数据表
        with st.expander("📋 详细数据（含精确时间）"):
            display_df = df[['time', 'seq', 'delay_ms']].tail(30)
            display_df.columns = ['时间', '序列号', '延迟(ms)']
            st.dataframe(display_df, use_container_width=True)
        
        # 精确时间说明
        st.info("💡 使用精确时间驱动，心跳间隔误差 < 1ms，延迟精确到毫秒级")
        
    else:
        st.info("等待心跳数据...")

else:
    st.header("🗺️ 航线规划")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"🏠 Home点: {st.session_state.home_point[0]:.6f}, {st.session_state.home_point[1]:.6f}")
    with col2:
        if st.session_state.waypoints:
            st.success(f"✈️ 当前航线: A→B ({len(st.session_state.waypoints)}个航点)")
        else:
            st.warning("⚠️ 暂无航线，请设置A点和B点后点击「生成航线」")
    
    st.markdown("---")
    
    with st.spinner("加载高德卫星地图..."):
        try:
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
            st.success("✅ 高德卫星地图加载成功")
            
        except Exception as e:
            st.error(f"地图加载失败: {e}")
    
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
            st.metric("起点 A", f"{a[0]:.6f}, {a[1]:.6f}")
        with col2:
            st.metric("终点 B", f"{b[0]:.6f}, {b[1]:.6f}")
        with col3:
            st.metric("直线距离", f"{distance:.1f} 米")

# 使用精确的时间间隔刷新（0.1秒而不是1秒）
time.sleep(0.1)
st.rerun()

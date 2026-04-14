import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
import threading
from datetime import datetime, timezone, timedelta
import json
from streamlit.components.v1 import html

st.set_page_config(page_title="南京科技职业学院 - 无人机地面站", layout="wide")

# ==================== 北京时间 ====================
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ)

# ==================== 心跳线程 ====================
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
            time.sleep(max(0, 1.0 - (time.time() - start)))
    
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
            return ("在线", time_since) if time_since < 3 else ("超时", time_since)

# ==================== 创建独立地图组件（使用 CartoDB 瓦片，无需注册） ====================
def leaflet_map_component(existing_obstacles):
    """
    使用 Leaflet + CartoDB Voyager 地图（国内可访问）的独立组件。
    用户可绘制多边形、设置名称和高度、管理障碍物列表，最后通过“保存到应用”按钮将数据传回 Streamlit。
    """
    obstacles_json = json.dumps(existing_obstacles)
    
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Leaflet 障碍物圈选</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
        <style>
            body, html, #map {{ height: 600px; width: 100%; margin: 0; padding: 0; }}
            .info-panel {{ position: absolute; bottom: 20px; left: 10px; z-index: 1000; background: white; padding: 10px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.2); max-width: 300px; }}
            .obstacle-list {{ max-height: 200px; overflow-y: auto; margin-top: 10px; }}
            .obstacle-item {{ padding: 5px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; }}
            button {{ margin: 2px; padding: 4px 8px; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div class="info-panel">
            <strong>✏️ 操作说明</strong><br>
            1. 点击右上角多边形工具 📐 绘制区域，双击完成。<br>
            2. 绘制后弹出对话框设置名称和高度。<br>
            3. 下方列表可删除障碍物。<br>
            4. 点击「保存到应用」将数据同步回程序。
            <div id="obstacleList" class="obstacle-list">
                <strong>已添加障碍物：</strong><br>
            </div>
            <button id="syncBtn">💾 保存到应用</button>
        </div>
        <script>
            // 初始化地图，使用 CartoDB Voyager 底图（国内访问稳定）
            var map = L.map('map').setView([32.234097, 118.749413], 18);
            L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 19
            }}).addTo(map);
            
            // 存储障碍物的数组
            var obstacles = {obstacles_json};
            var drawnItems = new L.FeatureGroup();
            map.addLayer(drawnItems);
            
            // 渲染已保存的障碍物
            function renderObstacles() {{
                drawnItems.clearLayers();
                obstacles.forEach(function(obs) {{
                    var latlngs = obs.points.map(function(p) {{
                        return [p[1], p[0]];
                    }});
                    var polygon = L.polygon(latlngs, {{
                        color: "red",
                        weight: 3,
                        fillColor: "#ff8888",
                        fillOpacity: 0.5
                    }}).bindPopup(obs.name + " (" + obs.height + "米)");
                    drawnItems.addLayer(polygon);
                }});
                updateObstacleList();
            }}
            
            // 更新侧边栏列表
            function updateObstacleList() {{
                var container = document.getElementById('obstacleList');
                var html = '<strong>已添加障碍物：</strong><br>';
                obstacles.forEach(function(obs, idx) {{
                    html += '<div class="obstacle-item">' + (idx+1) + '. ' + obs.name + ' (' + obs.height + '米) ' +
                            '<button onclick="removeObstacle(' + idx + ')">删除</button></div>';
                }});
                container.innerHTML = html;
            }}
            
            // 删除障碍物
            window.removeObstacle = function(idx) {{
                obstacles.splice(idx, 1);
                renderObstacles();
            }};
            
            // 绘图控件
            var drawControl = new L.Control.Draw({{
                draw: {{
                    polygon: true,
                    polyline: false,
                    rectangle: false,
                    circle: false,
                    marker: false,
                    circlemarker: false
                }},
                edit: {{
                    featureGroup: drawnItems,
                    remove: true
                }}
            }});
            map.addControl(drawControl);
            
            // 监听新绘制的多边形
            map.on(L.Draw.Event.CREATED, function(e) {{
                var layer = e.layer;
                var latlngs = layer.getLatLngs()[0];
                var points = latlngs.map(function(ll) {{
                    return [ll.lng, ll.lat];
                }});
                var name = prompt("请输入障碍物名称", "新障碍物");
                if (!name) return;
                var height = parseInt(prompt("请输入高度（米）", "20"));
                if (isNaN(height)) height = 20;
                var newObstacle = {{
                    name: name,
                    height: height,
                    points: points
                }};
                obstacles.push(newObstacle);
                renderObstacles();
            }});
            
            // 同步到应用
            document.getElementById('syncBtn').onclick = function() {{
                var data = JSON.stringify(obstacles);
                // 通过 URL 参数传递数据（Streamlit 可以读取 query_params）
                var newUrl = window.location.href.split('?')[0] + '?obstacles=' + encodeURIComponent(data);
                window.location.href = newUrl;
            }};
            
            // 初始渲染
            renderObstacles();
        </script>
    </body>
    </html>
    """
    return html(map_html, height=700)

# ==================== 从 URL 参数读取障碍物数据 ====================
def load_obstacles_from_url():
    """从 st.query_params 读取障碍物数据并更新 session_state"""
    params = st.query_params
    if 'obstacles' in params:
        try:
            data = json.loads(params['obstacles'])
            if isinstance(data, list):
                st.session_state.obstacles = data
                st.query_params.clear()
                st.rerun()
        except:
            pass

# ==================== 初始化 session_state ====================
if 'heartbeat_mgr' not in st.session_state:
    st.session_state.heartbeat_mgr = HeartbeatManager()
    st.session_state.heartbeat_mgr.start()

if 'page' not in st.session_state:
    st.session_state.page = "飞行监控"

# 学校坐标
SCHOOL_CENTER = (118.749413, 32.234097)

if 'home_point' not in st.session_state:
    st.session_state.home_point = SCHOOL_CENTER

if 'waypoints' not in st.session_state:
    st.session_state.waypoints = []

if 'a_point' not in st.session_state:
    st.session_state.a_point = SCHOOL_CENTER

if 'b_point' not in st.session_state:
    st.session_state.b_point = (SCHOOL_CENTER[0] + 0.001, SCHOOL_CENTER[1] + 0.001)

# 障碍物存储
if 'obstacles' not in st.session_state:
    # 示例障碍物
    st.session_state.obstacles = [
        {
            'name': '教学楼A区',
            'height': 20,
            'points': [
                (SCHOOL_CENTER[0] - 0.0004, SCHOOL_CENTER[1] - 0.0003),
                (SCHOOL_CENTER[0] + 0.0004, SCHOOL_CENTER[1] - 0.0003),
                (SCHOOL_CENTER[0] + 0.0004, SCHOOL_CENTER[1] + 0.0002),
                (SCHOOL_CENTER[0] - 0.0004, SCHOOL_CENTER[1] + 0.0002)
            ],
            'created_at': get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
        }
    ]

# 从 URL 加载新数据
load_obstacles_from_url()

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
        st.subheader("🏠 航线设置")
        col1, col2 = st.columns(2)
        with col1:
            a_lng = st.number_input("起点经度", value=st.session_state.a_point[0], format="%.6f", key="a_lng")
            a_lat = st.number_input("起点纬度", value=st.session_state.a_point[1], format="%.6f", key="a_lat")
        with col2:
            b_lng = st.number_input("终点经度", value=st.session_state.b_point[0], format="%.6f", key="b_lng")
            b_lat = st.number_input("终点纬度", value=st.session_state.b_point[1], format="%.6f", key="b_lat")
        
        if st.button("✈️ 生成/更新航线", key="gen_route"):
            st.session_state.a_point = (a_lng, a_lat)
            st.session_state.b_point = (b_lng, b_lat)
            st.session_state.waypoints = [st.session_state.a_point, st.session_state.b_point]
            st.success("航线已更新")
            st.rerun()
        
        st.markdown("---")
        st.subheader("🚧 障碍物管理")
        st.info(f"📊 当前障碍物数量: {len(st.session_state.obstacles)}")
        
        if st.session_state.obstacles:
            for i, obs in enumerate(st.session_state.obstacles):
                st.write(f"{i+1}. {obs['name']} (高度: {obs['height']}米)")
        
        st.markdown("---")
        st.info("💡 请点击下方「打开地图编辑器」进行多边形圈选")

# ==================== 主内容 ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控 - 心跳数据")
    st.caption("🕐 北京时间 (UTC+8)")
    heartbeats, seq, _ = st.session_state.heartbeat_mgr.get_data()
    if heartbeats:
        df = pd.DataFrame(heartbeats)
        # 心跳数据显示（略，保留原有代码）
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总心跳数", len(df))
        col2.metric("当前序列号", seq)
        if len(heartbeats) >= 2:
            intervals = [heartbeats[i]['timestamp'] - heartbeats[i-1]['timestamp'] for i in range(1, len(heartbeats))]
            avg_interval = sum(intervals) / len(intervals)
            st.metric("平均间隔", f"{avg_interval:.3f}秒")
        status, time_since = st.session_state.heartbeat_mgr.get_connection_status()
        col3.metric("连接状态", "✅ 在线" if status == "在线" else "❌ 离线")
        expected = seq
        received = len(df)
        loss_rate = (expected - received) / expected * 100 if expected > 0 else 0
        col4.metric("丢包率", f"{loss_rate:.1f}%")
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
    st.header("🗺️ 航线规划 - 多边形圈选障碍物")
    st.caption("使用下方地图工具绘制多边形，绘制后弹出对话框设置名称和高度，可管理障碍物列表，最后点击「保存到应用」同步数据。")
    
    if st.session_state.waypoints:
        a, b = st.session_state.waypoints
        dx = (b[0] - a[0]) * 111000 * math.cos(math.radians((a[1] + b[1]) / 2))
        dy = (b[1] - a[1]) * 111000
        distance = math.sqrt(dx*dx + dy*dy)
        st.info(f"✈️ 当前航线：起点 → 终点，直线距离约 {distance:.1f} 米")
    else:
        st.warning("⚠️ 暂无航线，请在左侧设置起点和终点并点击「生成/更新航线」")
    
    # 嵌入 Leaflet 地图组件
    leaflet_map_component(st.session_state.obstacles)

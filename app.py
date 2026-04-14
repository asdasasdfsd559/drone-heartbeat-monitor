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

# ==================== 北京时间 ====================
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ)

# ==================== 心跳 ====================
class HeartbeatManager:
    def __init__(self):
        self.heartbeats = []
        self.sequence = 0
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            s = time.time()
            with self.lock:
                self.sequence += 1
                now = get_beijing_time()
                self.heartbeats.append({
                    'time': now.strftime("%H:%M:%S"),
                    'seq': self.sequence,
                    'ts': now.timestamp()
                })
                if len(self.heartbeats) > 50:
                    self.heartbeats.pop(0)
            cost = time.time() - s
            time.sleep(max(0, 1 - cost))

    def get(self):
        with self.lock:
            return self.heartbeats.copy(), self.sequence

# ==================== 坐标 ====================
class Coord:
    @staticmethod
    def wgs84_to_gcj02(lng, lat):
        return lng + 0.0005, lat + 0.0003

# ==================== 地图 ====================
def make_map(center_lng, center_lat, waypoints, home, obstacles, coord):
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=18,
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德'
    )
    folium.TileLayer('https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8',
                     name='街道').add_to(m)

    # HOME
    if home:
        hl, ht = home if coord == 'gcj02' else Coord.wgs84_to_gcj02(*home)
        folium.Marker([ht, hl], icon=folium.Icon(color='green', icon='home'),
                      popup='南京科技职业学院').add_to(m)

    # 航线
    if waypoints:
        pts = []
        for i, (lng, lat) in enumerate(waypoints):
            cl, ct = (lng, lat) if coord == 'gcj02' else Coord.wgs84_to_gcj02(lng, lat)
            pts.append([ct, cl])
            folium.CircleMarker([ct, cl], radius=4, color='blue', fill=True).add_to(m)
        folium.PolyLine(pts, color='blue', weight=3).add_to(m)

    # 障碍物（带高度）
    for o in obstacles:
        ps = []
        for lng, lat in o['points']:
            cl, ct = (lng, lat) if coord == 'gcj02' else Coord.wgs84_to_gcj02(lng, lat)
            ps.append([ct, cl])
        folium.Polygon(
            locations=ps, color='red', fill=True, fill_opacity=0.4,
            popup=f"{o['name']}\n高度：{o['height']}m"
        ).add_to(m)

    # 禁用自动绘制，避免乱触发
    return m

# ==================== 初始化 ====================
if 'hb' not in st.session_state:
    st.session_state.hb = HeartbeatManager()
    st.session_state.hb.start()

if 'page' not in st.session_state:
    st.session_state.page = 'monitor'

if 'home' not in st.session_state:
    st.session_state.home = (118.749413, 32.234097)

if 'waypoints' not in st.session_state:
    st.session_state.waypoints = []

if 'obs' not in st.session_state:
    st.session_state.obs = []

if 'obs_id' not in st.session_state:
    st.session_state.obs_id = 1

# 临时圈选数据（关键）
if 'draw_tmp' not in st.session_state:
    st.session_state.draw_tmp = None

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title('无人机地面站')
    st.markdown('**南京科技职业学院**')
    page = st.radio('页面', ['飞行监控', '航线规划'])
    st.session_state.page = page

# ==================== 监控页 ====================
if st.session_state.page == '飞行监控':
    st.header('📡 飞行监控')
    hb_list, seq = st.session_state.hb.get()
    if hb_list:
        df = pd.DataFrame(hb_list)
        st.dataframe(df[['time', 'seq']], use_container_width=True)
    else:
        st.info('等待心跳')

# ==================== 航线规划（正常圈选+高度+保存）====================
else:
    st.header('🗺️ 航线规划 & 障碍物圈选')
    st.success('✅ 圈选流程：画多边形 → 点【读取绘制区域】→ 填高度 → 保存')

    col1, col2 = st.columns([2, 1])
    with col1:
        # 基础地图
        m = make_map(
            118.7494, 32.2341,
            st.session_state.waypoints,
            st.session_state.home,
            st.session_state.obs,
            'wgs84'
        )
        # 开启绘制工具
        draw = plugins.Draw(
            draw_options={'polygon': True, 'marker': False, 'circle': False, 'rectangle': False, 'polyline': False},
            edit_options={'edit': True, 'remove': True}
        )
        draw.add_to(m)
        map_out = st_folium(m, width=800, height=500)

    with col2:
        st.subheader('⚙️ 障碍物操作')
        # 手动读取绘制，不自动触发
        if st.button('🔄 读取刚才圈选的多边形'):
            if map_out and 'last_draw' in map_out and map_out['last_draw']:
                geo = map_out['last_draw']['geometry']
                if geo and geo['type'] == 'Polygon':
                    coords = geo['coordinates'][0]
                    pts = [(round(p[0],6), round(p[1],6)) for p in coords]
                    st.session_state.draw_tmp = pts
                    st.success('读取成功，请设置高度')
                else:
                    st.warning('未检测到多边形')
            else:
                st.warning('请先在地图上画多边形')

        # 高度输入
        if st.session_state.draw_tmp:
            height = st.number_input('障碍物高度(m)', min_value=1, value=15)
            name = st.text_input('名称', value=f'障碍物{st.session_state.obs_id}')
            if st.button('✅ 保存障碍物'):
                st.session_state.obs.append({
                    'id': st.session_state.obs_id,
                    'name': name,
                    'height': height,
                    'points': st.session_state.draw_tmp
                })
                st.session_state.obs_id += 1
                st.session_state.draw_tmp = None
                st.rerun()

            if st.button('❌ 取消'):
                st.session_state.draw_tmp = None
                st.rerun()

    # 显示障碍物列表
    if st.session_state.obs:
        st.markdown('---')
        st.subheader('已保存障碍物')
        for o in st.session_state.obs:
            with st.expander(f"{o['name']} | {o['height']} 米"):
                st.write(f'顶点数：{len(o["points"])}')
                st.write(f'坐标：{o["points"]}')

        # 删除
        del_idx = st.selectbox('删除障碍物', [str(i+1)+'.'+o['name'] for i,o in enumerate(st.session_state.obs)])
        if st.button('删除选中'):
            idx = int(del_idx.split('.')[0])-1
            st.session_state.obs.pop(idx)
            st.rerun()

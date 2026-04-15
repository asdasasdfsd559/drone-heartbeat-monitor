import streamlit as st
import pandas as pd
import datetime
import json
import os
import folium
from streamlit_folium import st_folium
import time

st.set_page_config(page_title="南京科技职业学院无人机地面站", layout="wide")

# ==================== 坐标转换 ====================
class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng,lat):
        return lng+0.0005, lat+0.0003
    @staticmethod
    def gcj02_to_wgs84(lng,lat):
        return lng-0.0005, lat-0.0005

# ==================== 地图 ====================
def create_map(center_lng,center_lat,waypoints,home_point,obstacles,coord_system,temp_points):
    m=folium.Map(
        location=[center_lat,center_lng],
        zoom_start=19,
        control_scale=True,
        tiles=None
    )

    folium.TileLayer(
        tiles='https://wprd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=2&style=8&x={x}&y={y}&z={z}',
        attr='高德-2026最新街道', name='街道图(2026)'
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri-2026高清卫星', name='卫星图(超清)'
    ).add_to(m)

    if home_point:
        h_lng,h_lat=home_point if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*home_point)
        folium.Marker(
            [h_lat,h_lng],
            icon=folium.Icon(color='green',icon='home'),
            popup="南京科技职业学院\n📍 江北新区葛关路625号/欣乐路188号"
        ).add_to(m)
        folium.Circle(radius=120,location=[h_lat,h_lng],color='green',fill=True,fill_opacity=0.3).add_to(m)
    
    if waypoints:
        pts=[]
        for wp in waypoints:
            w_lng,w_lat=wp if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*wp)
            pts.append([w_lat,w_lng])
        folium.PolyLine(pts,color='blue',weight=4).add_to(m)
    
    for ob in obstacles:
        ps=[]
        for p in ob['points']:
            plng,plat=p if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*p)
            ps.append([plat,plng])
        folium.Polygon(
            locations=ps,color='red',fill=True,fill_opacity=0.5,
            popup=f"{ob['name']} | {ob['height']}m"
        ).add_to(m)
    
    if len(temp_points)>=3:
        ps=[[lat,lng] for lng,lat in temp_points]
        folium.Polygon(locations=ps,color='red',weight=3,fill_opacity=0.3).add_to(m)
    for lng,lat in temp_points:
        folium.CircleMarker(location=[lat,lng],radius=5,color='red',fill=True).add_to(m)

    folium.LayerControl().add_to(m)
    return m

# ==================== 保存 ====================
STATE_FILE = "ground_station_state.json"

def save_state():
    state = {
        "home_point": st.session_state.home_point,
        "waypoints": st.session_state.waypoints,
        "a_point": st.session_state.a_point,
        "b_point": st.session_state.b_point,
        "coord_system": st.session_state.coord_system,
        "obstacles": st.session_state.obstacles,
        "draw_points": st.session_state.draw_points
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# ==================== 初始化 ====================
if 'page' not in st.session_state:
    st.session_state.page="飞行监控"

loaded = load_state()

OFFICIAL_LNG = 118.749413
OFFICIAL_LAT = 32.234097

defaults = {
    "home_point": (OFFICIAL_LNG, OFFICIAL_LAT),
    "waypoints": [],
    "a_point": (OFFICIAL_LNG, OFFICIAL_LAT),
    "b_point": (OFFICIAL_LNG + 0.0010, OFFICIAL_LAT + 0.0010),
    "coord_system": "gcj02",
    "obstacles": [],
    "draw_points": [],
    "last_click": None
}

for k, v in defaults.items():
    if loaded and k in loaded:
        st.session_state[k] = loaded[k]
    elif k not in st.session_state:
        st.session_state[k] = v

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🎮 无人机地面站")
    st.markdown("**南京科技职业学院**")
    st.caption("📍 葛关路625号 | 欣乐路188号")

    page=st.radio("功能",["📡 飞行监控","🗺️ 航线规划"])
    st.session_state.page=page
    
    st.success(f"✅ 在线")
    st.metric("状态","运行正常")

    if "🗺️ 航线规划" in page:
        st.session_state.coord_system=st.selectbox(
            "坐标系",["gcj02","wgs84"],format_func=lambda x:"GCJ02国内标准" if x=="gcj02" else "WGS84(GPS)"
        )
        st.subheader("🏫 学校中心点")
        hlng=st.number_input("经度",value=st.session_state.home_point[0],format="%.6f")
        hlat=st.number_input("纬度",value=st.session_state.home_point[1],format="%.6f")
        if st.button("更新中心点"):
            st.session_state.home_point=(hlng,hlat)
            save_state()

        st.subheader("✈️ 航线点")
        alng=st.number_input("A经度",value=st.session_state.a_point[0],format="%.6f")
        alat=st.number_input("A纬度",value=st.session_state.a_point[1],format="%.6f")
        blng=st.number_input("B经度",value=st.session_state.b_point[0],format="%.6f")
        blat=st.number_input("B纬度",value=st.session_state.b_point[1],format="%.6f")
        c1,c2=st.columns(2)
        with c1:
            if st.button("生成航线"):
                st.session_state.waypoints=[(alng,alat),(blng,blat)]
                save_state()
        with c2:
            if st.button("清空航线"):
                st.session_state.waypoints=[]
                save_state()

        st.subheader("🚧 圈选障碍物")
        height=st.number_input("高度(m)",1,500,25)
        name=st.text_input("名称","教学楼")
        if st.button("✅ 保存障碍物"):
            if len(st.session_state.draw_points)>=3:
                st.session_state.obstacles.append({"name":name,"height":height,"points":st.session_state.draw_points.copy()})
                st.session_state.draw_points=[]
                save_state()
        if st.button("❌ 清空当前打点"):
            st.session_state.draw_points=[]

# ==================== 心跳模块（无任何刷新 绝不加载） ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控")

    # 初始化
    if "heartbeat_data" not in st.session_state:
        st.session_state.heartbeat_data = []
        st.session_state.seq = 0
        st.session_state.last_update = 0

    # 按钮
    c1, c2 = st.columns(2)
    with c1:
        start = st.button("▶️ 开始心跳", use_container_width=True)
    with c2:
        stop = st.button("⏸️ 暂停心跳", use_container_width=True)

    if start:
        st.session_state.seq += 1
        t = datetime.datetime.now().strftime("%H:%M:%S")
        st.session_state.heartbeat_data.append({
            "序号": st.session_state.seq,
            "时间": t,
            "状态": "在线"
        })
        if len(st.session_state.heartbeat_data) > 30:
            st.session_state.heartbeat_data.pop(0)

    if stop:
        pass

    # 显示图表 + 表格
    df = pd.DataFrame(st.session_state.heartbeat_data)
    if not df.empty:
        st.subheader("心跳趋势")
        st.line_chart(df, x="序号", y="序号", color="#00a8ff")
        st.dataframe(df, use_container_width=True)

# ==================== 航线规划 ====================
else:
    st.header("🗺️ 航线规划")
    if st.session_state.waypoints:
        clng,clat = st.session_state.home_point
    else:
        clng,clat = OFFICIAL_LNG, OFFICIAL_LAT

    map_container = st.empty()
    with map_container:
        m = create_map(
            clng, clat,
            st.session_state.waypoints,
            st.session_state.home_point,
            st.session_state.obstacles,
            st.session_state.coord_system,
            st.session_state.draw_points
        )
        o = st_folium(m, width=1100, height=650, key="MAP_FIXED_KEY")

    if o and o.get("last_clicked"):
        lat = o["last_clicked"]["lat"]
        lng = o["last_clicked"]["lng"]
        st.session_state.draw_points.append((lng,lat))
        save_state()

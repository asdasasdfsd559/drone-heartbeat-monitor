import streamlit as st
import json
import os
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="南京科技职业学院无人机地面站", layout="wide")

# ==================== 永久保存 ====================
SAVE_FILE = "obstacles.json"

def load_obstacles():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_obstacles(data):
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== 初始化 ====================
if 'obstacles' not in st.session_state:
    st.session_state.obstacles = load_obstacles()
if 'draw_points' not in st.session_state:
    st.session_state.draw_points = []
if 'last_click' not in st.session_state:
    st.session_state.last_click = None

# 官方坐标（欣乐路188号）
OFFICIAL_LNG = 118.749428
OFFICIAL_LAT = 32.234111

# ==================== 地图（强制显示正确校名） ====================
def create_correct_map(obstacles, draw_points):
    m = folium.Map(
        location=[OFFICIAL_LAT, OFFICIAL_LNG],
        zoom_start=19,
        control_scale=True,
        tiles=None
    )
    # 街道图（高德旧数据，但我们强制覆盖校名）
    folium.TileLayer(
        tiles='https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}',
        attr='高德街道图', name='街道图'
    ).add_to(m)
    # 卫星图
    folium.TileLayer(
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德卫星图', name='卫星图'
    ).add_to(m)

    # ✅ 强制显示正确校名（覆盖旧“化工学院”）
    folium.Marker(
        location=[OFFICIAL_LAT, OFFICIAL_LNG],
        icon=folium.Icon(color='blue', icon='university'),
        popup="<b>南京科技职业学院</b><br>官方地址：江北新区欣乐路188号",
        tooltip="南京科技职业学院（官方）"
    ).add_to(m)
    # 大标签强制显示在地图上
    folium.map.Marker(
        [OFFICIAL_LAT, OFFICIAL_LNG],
        icon=folium.DivIcon(
            icon_size=(250, 36),
            icon_anchor=(125, -10),
            html='<div style="font-size:16px; font-weight:bold; color:blue; background:white; padding:4px; border-radius:4px;">南京科技职业学院（官方）</div>'
        )
    ).add_to(m)

    # 障碍物
    for ob in st.session_state.obstacles:
        points = [[p[1], p[0]] for p in ob['points']]
        folium.Polygon(
            locations=points, color='red', fill=True, fill_opacity=0.5,
            popup=f"{ob['name']} | {ob['height']}m"
        ).add_to(m)
    # 临时圈选
    if len(draw_points) >= 3:
        temp = [[p[1], p[0]] for p in draw_points]
        folium.Polygon(locations=temp, color='red', weight=3, fill_opacity=0.3).add_to(m)
    for p in draw_points:
        folium.CircleMarker(location=[p[1], p[0]], radius=5, color='red', fill=True).add_to(m)

    folium.LayerControl().add_to(m)
    return m

# ==================== 界面 ====================
st.title("🗺️ 南京科技职业学院 — 无人机地面站")
st.success("✅ 街道图+卫星图 | ✅ 永久记忆 | ✅ 强制显示正确校名")

col1, col2 = st.columns([3, 1])
with col2:
    st.subheader("🚧 障碍物编辑")
    height = st.number_input("障碍物高度 (m)", 1, 500, 25)
    name = st.text_input("名称", "教学楼/操场")
    if st.button("✅ 保存障碍物（永久）"):
        if len(st.session_state.draw_points) >= 3:
            st.session_state.obstacles.append({
                "name": name,
                "height": height,
                "points": st.session_state.draw_points.copy()
            })
            save_obstacles(st.session_state.obstacles)
            st.session_state.draw_points = []
            st.rerun()
        else:
            st.warning("至少3个点")
    if st.button("❌ 清空当前打点"):
        st.session_state.draw_points = []
        st.rerun()
    st.subheader("📋 已保存")
    for i, ob in enumerate(st.session_state.obstacles):
        if st.button(f"删除 {i+1}: {ob['name']}"):
            st.session_state.obstacles.pop(i)
            save_obstacles(st.session_state.obstacles)
            st.rerun()

with col1:
    m = create_correct_map(st.session_state.obstacles, st.session_state.draw_points)
    output = st_folium(m, width=1000, height=650, key="map")

# 点击打点
if output and output.get("last_clicked"):
    lat = output["last_clicked"]["lat"]
    lng = output["last_clicked"]["lng"]
    pt = (round(lng, 6), round(lat, 6))
    if pt != st.session_state.last_click:
        st.session_state.last_click = pt
        st.session_state.draw_points.append(pt)
        st.rerun()

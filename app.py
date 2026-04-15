import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import threading
from datetime import datetime, timezone, timedelta
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="南京科技职业学院无人机地面站", layout="wide")

# ==================== 北京时间 ====================
BEIJING_TZ = timezone(timedelta(hours=8))
def get_beijing_time():
    return datetime.now(BEIJING_TZ)
def get_beijing_time_ms():
    return get_beijing_time().strftime("%H:%M:%S.%f")[:-3]

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
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()
    def stop(self):
        self.running = False
        if self.thread: self.thread.join(timeout=2)
    def _heartbeat_loop(self):
        while self.running:
            s = time.time()
            with self.lock:
                self.sequence +=1
                now=get_beijing_time()
                self.heartbeats.append({
                    'time':now.strftime("%H:%M:%S"),
                    'time_ms':now.strftime("%H:%M:%S.%f")[:-3],
                    'seq':self.sequence,
                    'timestamp':now.timestamp()
                })
                if len(self.heartbeats)>100:
                    self.heartbeats.pop(0)
                self.last_time=now
            elapsed=time.time()-s
            time.sleep(max(0,1-elapsed))
    def get_data(self):
        with self.lock:
            return self.heartbeats.copy(), self.sequence, self.last_time
    def get_connection_status(self):
        with self.lock:
            if not self.heartbeats:
                return "等待",0
            last=self.heartbeats[-1]
            now=get_beijing_time()
            last_dt=datetime.fromtimestamp(last['timestamp'],tz=BEIJING_TZ)
            ts=(now-last_dt).total_seconds()
            return ("在线",ts) if ts<3 else ("超时",ts)

# ==================== 坐标转换 ====================
class CoordTransform:
    @staticmethod
    def wgs84_to_gcj02(lng,lat):
        return lng+0.0005, lat+0.0003
    @staticmethod
    def gcj02_to_wgs84(lng,lat):
        return lng-0.0005, lat-0.0003

# ==================== 地图（修复底图） ====================
def create_map(center_lng,center_lat,waypoints,home_point,obstacles,coord_system,temp_points):
    m=folium.Map(
        location=[center_lat,center_lng],
        zoom_start=18,
        control_scale=True,
        tiles=None # 手动加底图
    )
    # 国内可用底图（修复非卫星不显示）
    folium.TileLayer(
        tiles='https://webrd01.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scale=1',
        attr='高德路网', name='高德路网'
    ).add_to(m)
    folium.TileLayer(
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德卫星', name='高德卫星'
    ).add_to(m)
    folium.TileLayer(
        tiles='https://t0.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}',
        attr='天地图', name='天地图'
    ).add_to(m)

    # Home
    if home_point:
        h_lng,h_lat=home_point if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*home_point)
        folium.Marker([h_lat,h_lng],icon=folium.Icon(color='green',icon='home'),
                      popup="学校中心点").add_to(m)
        folium.Circle(radius=100,location=[h_lat,h_lng],color='green',fill=True).add_to(m)
    # 航线
    if waypoints:
        pts=[]
        for wp in waypoints:
            w_lng,w_lat=wp if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*wp)
            pts.append([w_lat,w_lng])
        folium.PolyLine(pts,color='blue',weight=3).add_to(m)
    # 障碍物
    for ob in obstacles:
        ps=[]
        for p in ob['points']:
            plng,plat=p if coord_system=='gcj02' else CoordTransform.wgs84_to_gcj02(*p)
            ps.append([plat,plng])
        folium.Polygon(locations=ps,color='red',fill=True,fill_opacity=0.4,
                       popup=f"{ob['name']} | {ob['height']}m").add_to(m)
    # 临时多边形
    if len(temp_points)>=3:
        ps=[[lat,lng] for lng,lat in temp_points]
        folium.Polygon(locations=ps,color='red',weight=3,fill_opacity=0.3).add_to(m)
    # 打点
    for lng,lat in temp_points:
        folium.CircleMarker(location=[lat,lng],radius=4,color='red',fill=True).add_to(m)
    folium.LayerControl().add_to(m)
    return m

# ==================== 初始化（修复session保存） ====================
if 'heartbeat_mgr' not in st.session_state:
    st.session_state.heartbeat_mgr=HeartbeatManager()
    st.session_state.heartbeat_mgr.start()

if 'page' not in st.session_state:
    st.session_state.page="飞行监控"

# 核心记忆
keys=['home_point','waypoints','a_point','b_point','coord_system','obstacles','draw_points','last_click']
defaults=[
    (118.749413,32.234097), [],
    (118.749413,32.234097), (118.750500,32.235200),
    'wgs84', [], [], None
]
for k,v in zip(keys,defaults):
    if k not in st.session_state:
        st.session_state[k]=v

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🎮 无人机地面站")
    st.markdown("**南京科技职业学院**")
    page=st.radio("功能",["📡 飞行监控","🗺️ 航线规划"])
    st.session_state.page=page
    status,ts=st.session_state.heartbeat_mgr.get_connection_status()
    _,seq,_=st.session_state.heartbeat_mgr.get_data()
    if status=="在线":
        st.success(f"✅ 在线 ({ts:.1f}s)")
    else:
        st.error(f"❌ 超时 ({ts:.1f}s)")
    st.metric("序列号",seq)

    if "🗺️ 航线规划" in page:
        st.session_state.coord_system=st.selectbox(
            "坐标系",["wgs84","gcj02"],format_func=lambda x:"WGS84" if x=="wgs84" else "GCJ02"
        )
        st.subheader("中心点")
        hlng=st.number_input("经度",value=st.session_state.home_point[0],format="%.6f")
        hlat=st.number_input("纬度",value=st.session_state.home_point[1],format="%.6f")
        if st.button("更新中心点"):
            st.session_state.home_point=(hlng,hlat)
            st.rerun()

        st.subheader("航线")
        alng=st.number_input("A经度",value=st.session_state.a_point[0],format="%.6f")
        alat=st.number_input("A纬度",value=st.session_state.a_point[1],format="%.6f")
        blng=st.number_input("B经度",value=st.session_state.b_point[0],format="%.6f")
        blat=st.number_input("B纬度",value=st.session_state.b_point[1],format="%.6f")
        c1,c2=st.columns(2)
        with c1:
            if st.button("生成航线"):
                st.session_state.a_point=(alng,alat)
                st.session_state.b_point=(blng,blat)
                st.session_state.waypoints=[st.session_state.a_point,st.session_state.b_point]
        with c2:
            if st.button("清空航线"):
                st.session_state.waypoints=[]

        st.subheader("🚧 圈选障碍物（点击地图）")
        st.write(f"已打点：{len(st.session_state.draw_points)}")
        height=st.number_input("高度(m)",1,500,20)
        name=st.text_input("名称","障碍物")

        # 保存（修复）
        if st.button("✅ 保存障碍物"):
            if len(st.session_state.draw_points)>=3:
                st.session_state.obstacles.append({
                    "name":name,"height":height,"points":st.session_state.draw_points.copy()
                })
                st.session_state.draw_points=[]
                st.success("保存成功 ✅ 已记忆")
                st.rerun()
            else:
                st.warning("至少3点")
        if st.button("❌ 清空当前打点"):
            st.session_state.draw_points=[]
            st.rerun()

        st.subheader("已保存障碍物")
        obs_names=[f"{i+1}. {o['name']} ({o['height']}m)" for i,o in enumerate(st.session_state.obstacles)]
        if obs_names:
            selected=st.selectbox("选择删除",obs_names)
            if st.button("删除选中"):
                idx=int(selected.split(".")[0])-1
                st.session_state.obstacles.pop(idx)
                st.rerun()
        if st.button("🗑️ 清空所有障碍物"):
            st.session_state.obstacles=[]
            st.rerun()

# ==================== 飞行监控 ====================
if "飞行监控" in st.session_state.page:
    st.header("📡 飞行监控")
    hb_list,seq,_=st.session_state.heartbeat_mgr.get_data()
    if hb_list:
        df=pd.DataFrame(hb_list)
        col1,col2,col3,col4=st.columns(4)
        col1.metric("总心跳",len(df))
        col2.metric("序列号",seq)
        col3.metric("状态","✅ 在线" if status=="在线" else "❌ 离线")
        col4.metric("丢包率",f"{(seq-len(df))/seq*100:.1f}%" if seq>0 else "0%")

        if len(hb_list)>=2:
            intervals=[hb_list[i]['timestamp']-hb_list[i-1]['timestamp'] for i in range(1,len(hb_list))]
            seqs=[x['seq'] for x in hb_list[1:]]
            fig_int=go.Figure()
            fig_int.add_trace(go.Scatter(x=seqs,y=intervals,mode='lines+markers',name='间隔',line=dict(color='orange')))
            fig_int.add_hline(y=1,line_dash='dash',line_color='green',annotation_text='目标1秒')
            fig_int.update_layout(title='心跳间隔',xaxis_title='seq',yaxis_title='s',height=300)
            st.plotly_chart(fig_int,use_container_width=True)

        fig_seq=go.Figure()
        fig_seq.add_trace(go.Scatter(x=df['time'],y=df['seq'],mode='lines+markers',name='seq',line=dict(color='blue')))
        fig_seq.update_layout(title='心跳趋势',xaxis_title='时间',yaxis_title='seq',height=300)
        st.plotly_chart(fig_seq,use_container_width=True)
        st.subheader("心跳数据")
        st.dataframe(df[['time_ms','seq']].tail(15),use_container_width=True)
    else:
        st.info("等待心跳...")

# ==================== 航线规划（修复点击保存） ====================
else:
    st.header("🗺️ 航线规划（圈选记忆版）")
    st.success("✅ 底图正常、障碍物永久保存")
    if st.session_state.waypoints:
        allp=[st.session_state.home_point]+st.session_state.waypoints
        clng=sum(p[0] for p in allp)/len(allp)
        clat=sum(p[1] for p in allp)/len(allp)
    else:
        clng,clat=st.session_state.home_point

    m=create_map(
        clng,clat,
        st.session_state.waypoints,
        st.session_state.home_point,
        st.session_state.obstacles,
        st.session_state.coord_system,
        st.session_state.draw_points
    )
    o=st_folium(m,width=1000,height=600,key="map")

    # 点击打点（修复：去重+锁）
    if o and o.get("last_clicked"):
        lat=o["last_clicked"]["lat"]
        lng=o["last_clicked"]["lng"]
        current_click=(round(lng,6),round(lat,6))
        # 防重复
        if current_click != st.session_state.get("last_click",None):
            st.session_state.last_click=current_click
            st.session_state.draw_points.append(current_click)
            st.rerun()

# 自动刷新监控
if "飞行监控" in st.session_state.page:
    time.sleep(0.5)
    st.rerun()

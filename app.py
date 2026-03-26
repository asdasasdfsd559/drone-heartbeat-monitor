import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime

st.set_page_config(page_title="无人机监控", layout="wide")

st.title("🚁 无人机心跳监控系统")

# 初始化数据
if 'heartbeats' not in st.session_state:
    st.session_state.heartbeats = []
    st.session_state.sequence = 0
    st.session_state.last_time = datetime.now()

# 自动生成心跳（每秒一次）
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

# 显示数据
if st.session_state.heartbeats:
    df = pd.DataFrame(st.session_state.heartbeats)
    
    # 统计卡片
    col1, col2, col3 = st.columns(3)
    
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
            st.error(f"⚠️ 超时！{time_since}秒未收到心跳")
    
    # 绘制图表
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['time'],
        y=df['seq'],
        mode='lines+markers',
        name='心跳',
        line=dict(color='blue', width=2),
        marker=dict(size=8, color='red')
    ))
    
    fig.update_layout(
        title="心跳序列号变化",
        xaxis_title="时间",
        yaxis_title="序列号",
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 数据表
    with st.expander("查看详细数据"):
        st.dataframe(df.tail(20), use_container_width=True)
else:
    st.info("等待数据生成...")

# 自动刷新
time.sleep(1)
st.rerun()

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import os

st.set_page_config(page_title="心跳监控", layout="wide")

st.title("🚁 无人机心跳监控系统")

# 侧边栏
with st.sidebar:
    st.header("设置")
    auto_refresh = st.checkbox("自动刷新", value=True)
    refresh_seconds = st.slider("刷新间隔(秒)", 1, 5, 2, disabled=not auto_refresh)
    
    if st.button("清空数据"):
        if os.path.exists("heartbeat.txt"):
            os.remove("heartbeat.txt")
        st.success("数据已清空")
        time.sleep(1)
        st.rerun()

# 读取数据
if os.path.exists("heartbeat.txt"):
    try:
        # 读取文件
        with open("heartbeat.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if lines:
            # 解析数据
            times = []
            sequences = []
            
            for line in lines:
                if "," in line:
                    parts = line.strip().split(",")
                    if len(parts) == 2:
                        times.append(parts[0])
                        sequences.append(int(parts[1]))
            
            # 创建DataFrame
            df = pd.DataFrame({
                "时间": times,
                "序列号": sequences
            })
            
            # 显示统计
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("总心跳数", len(df))
            
            with col2:
                if len(df) > 0:
                    last_time = df["时间"].iloc[-1]
                    st.metric("最后心跳", last_time)
                else:
                    st.metric("最后心跳", "无")
            
            with col3:
                import datetime
                current = datetime.datetime.now().strftime("%H:%M:%S")
                st.metric("当前时间", current)
            
            # 显示图表
            if len(df) > 0:
                st.subheader("📈 心跳序列图")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["时间"],
                    y=df["序列号"],
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
                
                # 显示数据表
                with st.expander("查看详细数据"):
                    st.dataframe(df.tail(20), use_container_width=True)
            else:
                st.info("等待心跳数据...")
        else:
            st.info("等待心跳数据...")
            
    except Exception as e:
        st.error(f"读取数据出错: {e}")
        st.info("请确保模拟器正在运行")
else:
    st.info("📡 等待心跳数据...")
    st.code("请先运行模拟器:\npython simulator.py")
    st.info("提示：模拟器需要持续运行才能接收数据")

# 自动刷新
if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
import threading
from datetime import datetime, timezone, timedelta
import folium
from streamlit_folium import st_folium
import json
from streamlit.components.v1 import html

st.set_page_config(page_title="南京科技职业学院 - 无人机地面站", layout="wide")

# ==================== 北京时间 ====================
BEIJING_TZ = timezone(timedelta(hours=8))
def get_beijing_time():
    return datetime.now(BEIJING_TZ)

# ==================== 心跳线程 (为保持代码完整性保留，在此方案中未使用) ====================
class HeartbeatManager:
    # ... (心跳线程代码，因篇幅原因省略，但保留在你的项目中即可)
    pass

# ==================== 内嵌绘图工具（核心修复部分） ====================
def drawing_tool():
    """
    返回一个独立的 HTML 组件，包含：
    - 地图（高德卫星图）
    - 多边形绘制工具（Leaflet.draw）
    - 左侧面板：障碍物列表（名称、高度），支持删除
    - 按钮：保存到应用
    """
    # 读取当前已保存的障碍物
    obstacles = st.session_state.get('obstacles', [])
    obstacles_json = json.dumps(obstacles)

    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>障碍物圈选工具</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
        <style>
            /* ... (样式代码，与之前相同，确保控制面板显示正常) ... */
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body, html, #map {{ height: 100%; width: 100%; }}
            .toolbar {{
                position: absolute; top: 10px; left: 10px; z-index: 1000;
                background: white; padding: 10px; border-radius: 8px;
                box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 260px;
                max-height: 80%; overflow-y: auto; font-family: sans-serif;
            }}
            /* ... (其余样式与之前一致) ... */
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div class="toolbar">
            <h3>✏️ 障碍物管理</h3>
            <button id="drawBtn">➕ 绘制多边形</button>
            <button id="saveBtn" style="background:#52c41a;">💾 保存到应用</button>
            <div class="obstacle-list" id="obstacleList">
                <strong>已添加障碍物：</strong><br>
            </div>
            <div class="status" id="status">状态：就绪</div>
        </div>
        <script>
            // 修复的核心：使用更可靠的高德瓦片URL，并正确转义JavaScript字符串
            var map = L.map('map').setView([32.234097, 118.749413], 18);
            // 使用一个更稳定且不需要额外配置的高德地图瓦片URL
            L.tileLayer('https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}', {{
                attribution: '高德地图',
                maxZoom: 18
            }}).addTo(map);

            // 障碍物数据
            var obstacles = {obstacles_json};
            var drawnItems = new L.FeatureGroup();
            map.addLayer(drawnItems);
            var currentDrawControl = null;

            // 渲染障碍物列表和地图上的多边形
            function render() {{
                drawnItems.clearLayers();
                obstacles.forEach(function(obs, idx) {{
                    var latlngs = obs.points.map(function(p) {{ return [p[1], p[0]]; }});
                    var poly = L.polygon(latlngs, {{
                        color: "red",
                        weight: 3,
                        fillColor: "#ff8888",
                        fillOpacity: 0.5
                    }}).bindPopup(obs.name + " (" + obs.height + "米)");
                    drawnItems.addLayer(poly);
                }});
                // 更新列表 (代码与之前相同)
                var container = document.getElementById('obstacleList');
                var html = '<strong>已添加障碍物：</strong><br>';
                obstacles.forEach(function(obs, idx) {{
                    html += '<div class="obstacle-item">' + (idx+1) + '. ' + obs.name + ' (' + obs.height + '米) ' +
                            '<button onclick="removeObstacle(' + idx + ')">删除</button></div>';
                }});
                container.innerHTML = html;
                document.getElementById('status').innerText = '状态：就绪，共 ' + obstacles.length + ' 个障碍物';
            }}

            window.removeObstacle = function(idx) {{
                obstacles.splice(idx, 1);
                render();
            }};

            function startDrawing() {{
                if (currentDrawControl) {{
                    map.removeControl(currentDrawControl);
                }}
                currentDrawControl = new L.Control.Draw({{
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
                map.addControl(currentDrawControl);
                new L.Draw.Polygon(map, currentDrawControl.options.draw.polygon).enable();
                document.getElementById('status').innerText = '状态：正在绘制多边形，点击地图添加顶点，双击完成';
            }}

            map.on(L.Draw.Event.CREATED, function(e) {{
                var layer = e.layer;
                var latlngs = layer.getLatLngs()[0];
                var points = latlngs.map(function(ll) {{ return [ll.lng, ll.lat]; }});
                var name = prompt("请输入障碍物名称", "新障碍物");
                if (!name) {{
                    if (currentDrawControl) map.removeControl(currentDrawControl);
                    return;
                }}
                var height = parseInt(prompt("请输入高度（米）", "20"));
                if (isNaN(height)) height = 20;
                obstacles.push({{
                    name: name,
                    height: height,
                    points: points
                }});
                render();
                if (currentDrawControl) map.removeControl(currentDrawControl);
                document.getElementById('status').innerText = '状态：已添加障碍物 "' + name + '"';
            }});

            document.getElementById('saveBtn').onclick = function() {{
                var data = JSON.stringify(obstacles);
                var newUrl = window.location.href.split('?')[0] + '?obstacles=' + encodeURIComponent(data);
                window.location.href = newUrl;
            }};
            document.getElementById('drawBtn').onclick = startDrawing;
            render();
        </script>
    </body>
    </html>
    """
    return html(map_html, height=700)

# ==================== 从 URL 参数读取障碍物 ====================
def load_obstacles_from_url():
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
# ... (初始化代码与之前相同，确保 `st.session_state.obstacles` 存在)
if 'obstacles' not in st.session_state:
    st.session_state.obstacles = []
load_obstacles_from_url()

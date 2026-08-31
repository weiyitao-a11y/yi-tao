import subprocess
import sys

# 自动安装缺少库，避免 Cloud 找不到 requirements.txt 的问题
packages = ["plotly", "requests", "pandas", "streamlit-autorun"]
for package in packages:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorun import autorun
from datetime import datetime

st.set_page_config(page_title="四方量化 - A股实时盯盘", layout="wide")

# 1. 自动刷新配置
st.sidebar.header("⚡ 盯盘配置")
refresh_interval = st.sidebar.slider("刷新间隔 (秒)", 1, 10, 3)
autorun(interval=refresh_interval * 1000)

# A 股代码输入
default_codes = "sh600519, sz000002, sz300750, sh601138"
codes_input = st.sidebar.text_input("盯盘标的 (代码用逗号隔开)", default_codes)
stock_codes = [c.strip().lower() for c in codes_input.split(",") if c.strip()]

# 2. 腾讯财经 API 行情解析函数
def fetch_qq_stock_data(codes):
    if not codes:
        return []
    url = f"http://qt.gtimg.cn/q={','.join(codes)}"
    try:
        resp = requests.get(url, timeout=3)
        text = resp.content.decode('gbk')
        lines = text.strip().split(';')
        data_list = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.split('=')
            if len(parts) < 2:
                continue
            code = parts[0].split('v_')[-1]
            vals = parts[1].strip('"').split('~')
            if len(vals) < 49:
                continue
            
            name = vals[1]
            current_price = float(vals[3])
            prev_close = float(vals[4])
            open_price = float(vals[5])
            high_price = float(vals[33])
            low_price = float(vals[34])
            
            change_val = current_price - prev_close
            change_pct = (change_val / prev_close) * 100 if prev_close else 0.0
            
            # 买一至买五，卖一至卖五
            bid_ask = {
                'buy': [
                    (float(vals[9]), int(vals[10])),
                    (float(vals[11]), int(vals[12])),
                    (float(vals[13]), int(vals[14])),
                    (float(vals[15]), int(vals[16])),
                    (float(vals[17]), int(vals[18]))
                ],
                'sell': [
                    (float(vals[19]), int(vals[20])),
                    (float(vals[21]), int(vals[22])),
                    (float(vals[23]), int(vals[24])),
                    (float(vals[25]), int(vals[26])),
                    (float(vals[27]), int(vals[28]))
                ]
            }
            
            data_list.append({
                'code': code,
                'name': name,
                'current': current_price,
                'prev_close': prev_close,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'change_val': change_val,
                'change_pct': change_pct,
                'bid_ask': bid_ask
            })
        return data_list
    except Exception as e:
        st.error(f"数据获取失败: {e}")
        return []

# 3. 页面布局与实时看板展示
st.title("📈 四方量化 - A股实时五档盘口控制台")
st.caption(f"最后更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

stocks_data = fetch_qq_stock_data(stock_codes)

if stocks_data:
    cols = st.columns(len(stocks_data))
    for i, stock in enumerate(stocks_data):
        with cols[i]:
            color = "red" if stock['change_val'] >= 0 else "green"
            st.subheader(f"{stock['name']} ({stock['code']})")
            
            st.metric(
                label="当前现价", 
                value=f"{stock['current']:.2f}", 
                delta=f"{stock['change_val']:.2f} ({stock['change_pct']:.2f}%)"
            )
            
            st.text(f"今开: {stock['open']:.2f} | 昨收: {stock['prev_close']:.2f}")
            st.text(f"最高: {stock['high']:.2f} | 最低: {stock['low']:.2f}")
            
            # 五档盘口绘制
            bids = stock['bid_ask']['buy']
            sells = stock['bid_ask']['sell']
            
            sell_prices = [s[0] for s in reversed(sells)]
            sell_vols = [s[1] for s in reversed(sells)]
            buy_prices = [b[0] for b in bids]
            buy_vols = [b[1] for b in bids]
            
            fig = go.Figure()
            
            # 卖盘（红/绿）
            fig.add_trace(go.Bar(
                y=[f"卖5 {sell_prices[0]}", f"卖4 {sell_prices[1]}", f"卖3 {sell_prices[2]}", f"卖2 {sell_prices[3]}", f"卖1 {sell_prices[4]}"],
                x=sell_vols,
                orientation='h',
                name='卖盘',
                marker_color='rgba(255, 99, 132, 0.6)'
            ))
            
            # 买盘（绿/红）
            fig.add_trace(go.Bar(
                y=[f"买1 {buy_prices[0]}", f"买2 {buy_prices[1]}", f"买3 {buy_prices[2]}", f"买4 {buy_prices[3]}", f"买5 {buy_prices[4]}"],
                x=buy_vols,
                orientation='h',
                name='买盘',
                marker_color='rgba(75, 192, 192, 0.6)'
            ))
            
            fig.update_layout(
                title="五档挂单量",
                height=300,
                margin=dict(l=10, r=10, t=30, b=10),
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("暂无数据，请检查左侧代码输入是否正确。")

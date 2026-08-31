import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorun import autorun
from datetime import datetime

st.set_page_config(page_title="四方量化 - A股实时盯盘控制台", layout="wide")

# 1. 自动刷新配置（默认每 3 秒刷新一次）
st.sidebar.header("⚡ 盯盘配置")
refresh_interval = st.sidebar.slider("刷新间隔 (秒)", 1, 10, 3)
autorun(interval=refresh_interval * 1000)

# A 股代码输入（支持 sh/sz 前缀自动识别）
default_codes = "sh600519, sz000002, sz300750, sh601138"
codes_input = st.sidebar.text_input("盯盘标的 (代码格式: sh600519 或 sz000002)", default_codes)
stock_codes = [c.strip().lower() for c in codes_input.split(",") if c.strip()]

# 2. 腾讯财经 API 行情解析函数
def fetch_qq_stock_data(codes):
    """
    通过腾讯财经公开 API 获取实时五档盘口与行情数据
    """
    if not codes:
        return {}
    
    url = f"http://qt.gtimg.cn/q={','.join(codes)}"
    try:
        resp = requests.get(url, timeout=2)
        resp.encoding = 'gbk' # 腾讯接口采用 GBK 编码
        data_str = resp.text
        
        result = {}
        for line in data_str.split(';'):
            if '="' in line:
                code_raw = line.split('=')[0].split('v_')[-1]
                content = line.split('="')[1].rstrip('"')
                fields = content.split('~')
                
                if len(fields) > 40:
                    result[code_raw] = {
                        "name": fields[1],            # 股票名称
                        "code": fields[2],            # 代码
                        "current": float(fields[3]),   # 当前价
                        "prev_close": float(fields[4]),# 昨收价
                        "open": float(fields[5]),      # 开盘价
                        "volume": float(fields[6]),    # 成交量(手)
                        "high": float(fields[33]),     # 最高价
                        "low": float(fields[34]),      # 最低价
                        "pct_change": float(fields[32]), # 涨跌幅 %
                        "turnover": float(fields[37]), # 成交额(万元)
                        # 买卖五档数据 (价格, 量)
                        "b1_p": float(fields[9]), "b1_v": int(fields[10]),
                        "b2_p": float(fields[11]), "b2_v": int(fields[12]),
                        "b3_p": float(fields[13]), "b3_v": int(fields[14]),
                        "a1_p": float(fields[19]), "a1_v": int(fields[20]),
                        "a2_p": float(fields[21]), "a2_v": int(fields[22]),
                        "a3_p": float(fields[23]), "a3_v": int(fields[24]),
                    }
        return result
    except Exception as e:
        st.error(f"获取实时行情失败: {e}")
        return {}

# 3. 主界面渲染
st.title("⚡ 四方量化 - A股实时盯盘控制台")
st.caption(f"数据源：腾讯财经公开接口 | 更新时间：{datetime.now().strftime('%H:%M:%S')} | 每 {refresh_interval} 秒自动刷盘")

realtime_data = fetch_qq_stock_data(stock_codes)

if realtime_data:
    # --- 顶栏：多股并发监控卡片 ---
    cols = st.columns(len(realtime_data))
    for idx, (code, info) in enumerate(realtime_data.items()):
        with cols[idx]:
            # 动态计算今日振幅
            amplitude = ((info['high'] - info['low']) / info['prev_close']) * 100 if info['prev_close'] > 0 else 0
            
            st.metric(
                label=f"{info['name']} ({code.upper()})",
                value=f"¥{info['current']:.2f}",
                delta=f"{info['pct_change']:.2f}%"
            )
            st.caption(f"高: {info['high']} | 低: {info['low']} | 振幅: {amplitude:.2f}%")

    st.divider()

    # --- 选中单股展示买卖五档盘口与突破分析 ---
    selected_code = st.selectbox(
        "选择深入盯盘标的", 
        options=list(realtime_data.keys()), 
        format_func=lambda x: f"{realtime_data[x]['name']} ({x.upper()})"
    )

    if selected_code and selected_code in realtime_data:
        s_info = realtime_data[selected_code]
        
        col_left, col_right = st.columns([1, 2])
        
        # 盘口买卖五档 (Level 1) 展示
        with col_left:
            st.subheader("📋 实时买卖盘口")
            order_book_data = {
                "档位": ["卖三", "卖二", "卖一", "买一", "买二", "买三"],
                "价格 (元)": [s_info['a3_p'], s_info['a2_p'], s_info['a1_p'], s_info['b1_p'], s_info['b2_p'], s_info['b3_p']],
                "挂单量 (手)": [s_info['a3_v'], s_info['a2_v'], s_info['a1_v'], s_info['b1_v'], s_info['b2_v'], s_info['b3_v']]
            }
            df_order_book = pd.DataFrame(order_book_data)
            st.dataframe(df_order_book, hide_index=True, use_container_width=True)

        # 盘中预警与监控
        with col_right:
            st.subheader("🚨 盘中关键位置与突破预警")
            
            # 预警逻辑判断
            curr = s_info['current']
            high = s_info['high']
            low = s_info['low']
            prev = s_info['prev_close']
            
            if curr >= high and curr > prev:
                st.error(f"🔥 强力警报: {s_info['name']} 当前价格 ({curr}) 正在创出【今日新高】！")
            elif curr <= low and curr < prev:
                st.success(f"❄️ 突破警报: {s_info['name']} 当前价格 ({curr}) 正在触及【今日新低】！")
            else:
                st.info(f"📊 盘整状态: 股价位于今日区间 [{low} ~ {high}] 之间震荡。")
            
            # 涨跌停距离指示器
            limit_up = round(prev * 1.1, 2)   # 主板 10% 涨停预估
            limit_down = round(prev * 0.9, 2) # 主板 10% 跌停预估
            
            dist_up = ((limit_up - curr) / curr) * 100
            st.write(f"• 预估涨停价: **{limit_up}** (距涨停还差 {dist_up:.2f}%)")
            st.write(f"• 今日总成交额: **{s_info['turnover'] / 10000:.2f} 亿元**")
            st.write(f"• 今日总成交量: **{int(s_info['volume'])} 手**")

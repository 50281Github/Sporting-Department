import os
import json
import requests
import importlib.util
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import time
import altair as alt
import pandas as pd


def import_progress_checker():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, 'progress_checker.py'),
        os.path.join(base_dir, '..', '进度检测提醒', 'progress_checker.py'),
        os.path.join(base_dir, '..', 'progress_checker.py'),
    ]
    for pc_path in candidates:
        if os.path.exists(pc_path):
            spec = importlib.util.spec_from_file_location('progress_checker', pc_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore
            return module
    raise FileNotFoundError('未找到 progress_checker.py，请确认文件位置。')


pc = import_progress_checker()

st.set_page_config(page_title='分拣进度实时看板', layout='wide')
# 页面标题
st.title('分拣进度实时看板')

# 刷新时间显示（移到标题下方）
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
st.markdown(f"""
<div style="text-align: right; color: #666; font-size: 12px; margin-bottom: 20px; margin-top: -10px;">
    <i class="fas fa-sync-alt"></i> 最后刷新: {current_time}
</div>
""", unsafe_allow_html=True)

# 在获取进度数据后添加动态鼓励内容
def get_encouragement_message(delta_pct, status, actual_pct):
    """根据进度情况生成动态鼓励内容"""
    # 特殊情况：任务已100%完成
    if actual_pct >= 100.0:
        messages = [
            "🎉 任务完成！完美收工！ ✨(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
            "🏆 大功告成！今日圆满！ 🎊(◡ ‿ ◡)🎊",
            "👑 100%达成！王者风范！ ᕕ( ᐛ )ᕗ",
            "🌟 完美收官！明日再战！ ヽ(°〇°)ﾉ",
            "🚀 任务清零！效率之王！ (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
            "💎 钻石品质！无懈可击！ ✨(◡ ‿ ◡)✨",
            "🎯 神级操作！百发百中！ ᕕ( ᐛ )ᕗ",
            "⚡ 闪电完成！速度传说！ ᕦ(ò_óˇ)ᕤ"
        ]
    elif delta_pct >= 5:
        messages = [
            "🚀 超棒！再接再厉！ (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
            "⭐ 进度领先！保持节奏！ ✨(◡ ‿ ◡)✨",
            "🎯 效率满分！继续冲刺！ ᕕ( ᐛ )ᕗ",
            "💪 太棒了！势不可挡！ ヽ(°〇°)ﾉ",
            "🌈 超神发挥！无人能敌！ (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
            "🔥 火力全开！碾压全场！ ᕕ( ᐛ )ᕗ"
        ]
    elif delta_pct >= 2:
        messages = [
            "👍 进度不错！稳步前进！ (｡◕‿◕｡)",
            "🌟 保持状态！加油加油！ ٩(◕‿◕)۶",
            "✨ 很好！继续努力！ (◠‿◠)",
            "🎉 节奏很棒！再加把劲！ ＼(^o^)／",
            "📈 稳扎稳打！步步为营！ (•̀ᴗ•́)و",
            "🎪 表现优秀！值得点赞！ ٩(◕‿◕)۶"
        ]
    elif delta_pct >= -1:
        messages = [
            "📈 稳中求进！继续加油！ (•̀ᴗ•́)و",
            "⚡ 保持节奏！你能行！ ᕦ(ò_óˇ)ᕤ",
            "🔥 加把劲！胜利在望！ (ง •̀_•́)ง",
            "💫 稳住！马上追上！ ٩(๑❛ᴗ❛๑)۶",
            "🎯 瞄准目标！精准出击！ (ง •̀_•́)ง",
            "🌊 乘风破浪！勇往直前！ ᕦ(ò_óˇ)ᕤ"
        ]
    elif delta_pct >= -3:
        messages = [
            "⏰ 时间紧迫！冲冲冲！ (╯°□°）╯",
            "🚨 需要加速！快快快！ ε=ε=ε=┌(;*´Д`)ﾉ",
            "⚡ 抓紧时间！追上去！ ᕕ(╯°□°)ᕗ",
            "🔔 加油催促！不要掉队！ (｡•̀ᴗ-)✧",
            "🏃‍♂️ 快马加鞭！时不我待！ ε=ε=ε=┌(;*´Д`)ﾉ",
            "⚠️ 黄牌警告！立即提速！ (╯°□°）╯"
        ]
    else:
        messages = [
            "🚨 紧急！全力冲刺！ (ﾟДﾟ≡ﾟДﾟ)",
            "⚠️ 落后较多！火速追赶！ Σ(°△°|||)︴",
            "🔥 危险！立即行动！ (╬ಠ益ಠ)",
            "💥 警报！全员加速！ ヽ(ﾟ〇ﾟ)ﾉ",
            "🆘 红色警报！刻不容缓！ (ﾟДﾟ≡ﾟДﾟ)",
            "⛔ 严重滞后！火力全开！ Σ(°△°|||)︴"
        ]
    
    import random
    return random.choice(messages)

# 主题与样式美化
st.markdown(
    """
    <style>
      .metric-card {background:#111827; padding:16px; border-radius:12px; border:1px solid #374151;}
      .status-pill {display:inline-block; padding:6px 10px; border-radius:20px; font-weight:600;}
      .status-ok {background:#DCFCE7; color:#166534;}
      .status-warn {background:#FEF3C7; color:#92400E;}
      .status-unknown {background:#E5E7EB; color:#374151;}
      /* 将标题往下移动，减少顶部空白 */
      .block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }
      h1 { margin-top: 1rem !important; margin-bottom: 0.8rem !important; }
      .status-pill { margin-top: 0.3rem; margin-bottom: 0.8rem; }
      [data-testid="metric-container"] { margin-bottom: 0.3rem !important; }
      
      /* 自定义数据指标样式 */
      .metrics-container {
        margin: 1rem 0;
      }
      .metric-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1rem;
      }
      .metric-item {
        flex: 1;
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
      }
      .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1f2937;
        margin-bottom: 0.5rem;
      }
      .metric-label {
        font-size: 0.9rem;
        color: #6b7280;
        font-weight: 500;
      }
      .metric-delta {
        font-size: 0.8rem;
        color: #059669;
        margin-top: 0.3rem;
        font-weight: 600;
      }
      
      /* 分类卡片样式 */
      .category-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: clamp(0.5rem, 2vw, 1rem);
        margin-bottom: 1rem;
      }
      .category-header {
        font-size: clamp(1rem, 3vw, 1.8rem);
        font-weight: bold;
        color: #1f2937;
        text-align: center;
        margin-bottom: clamp(0.4rem, 1.5vw, 0.8rem);
      }
      .category-metrics {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: clamp(0.1rem, 0.8vw, 0.6rem);
        flex-wrap: nowrap;
        overflow-x: auto;
        min-width: 0;
      }
      .category-metric {
        flex: 1 1 auto;
        min-width: fit-content;
        text-align: center;
        padding: 0 clamp(0.05rem, 0.3vw, 0.2rem);
        overflow: visible;
      }
      .category-metric .metric-value {
        font-size: clamp(0.8rem, 2.5vw, 1.6rem);
        font-weight: bold;
        color: #1f2937;
        margin-bottom: clamp(0.1rem, 0.5vw, 0.3rem);
        white-space: nowrap;
        overflow: visible;
        text-overflow: clip;
        word-break: keep-all;
      }
      .category-metric .metric-label {
        font-size: clamp(0.6rem, 1.8vw, 1rem);
        color: #6b7280;
        font-weight: 500;
        line-height: 1.2;
        white-space: nowrap;
        overflow: visible;
        text-overflow: clip;
        word-break: keep-all;
      }
      .category-metric .metric-delta {
        font-size: clamp(0.5rem, 1.5vw, 0.9rem);
        color: #059669;
        margin-top: clamp(0.1rem, 0.3vw, 0.2rem);
        font-weight: 600;
        white-space: nowrap;
        overflow: visible;
        text-overflow: clip;
        word-break: keep-all;
      }
      
      /* 隐藏可能的空白iframe */
      iframe[height="1"] { display: none !important; }
      
      /* 移动端响应式样式 */
      @media (max-width: 768px) {
        .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
        h1 { font-size: 1.8rem !important; text-align: center !important; }
        .status-pill { font-size: 0.9rem !important; }
        [data-testid="metric-container"] { 
          margin-bottom: 0.8rem !important; 
          text-align: center !important;
        }
        [data-testid="metric-container"] > div > div { text-align: center !important; }
        /* 数字容器字体大小优化 */
        [data-testid="metric-container"] [data-testid="metric-value"] {
          font-size: 1.5rem !important;
        }
        [data-testid="metric-container"] [data-testid="metric-label"] {
          font-size: 0.9rem !important;
        }
        [data-testid="metric-container"] [data-testid="metric-delta"] {
          font-size: 0.8rem !important;
        }
        .cmp-box { margin: 1rem 0 !important; }
        .cmp-legend { justify-content: center !important; }
        
        /* 自定义metrics移动端优化 */
      }
      
      /* 小屏幕优化 */
      @media (max-width: 480px) {
        h1 { font-size: 1.5rem !important; }
        .status-pill { font-size: 0.8rem !important; padding: 4px 8px !important; }
        [data-testid="metric-container"] { margin-bottom: 1rem !important; }
        /* 更小屏幕的数字容器优化 */
        [data-testid="metric-container"] [data-testid="metric-value"] {
          font-size: 1.2rem !important;
        }
        [data-testid="metric-container"] [data-testid="metric-label"] {
          font-size: 0.8rem !important;
        }
        [data-testid="metric-container"] [data-testid="metric-delta"] {
          font-size: 0.7rem !important;
        }
        
        /* 自定义metrics小屏幕优化 */
        .metric-row {
          gap: 0.3rem !important;
        }
        .metric-item {
          padding: 0.6rem !important;
        }
        .metric-value {
          font-size: 1.2rem !important;
        }
        .metric-label {
          font-size: 0.7rem !important;
        }
        .metric-delta {
          font-size: 0.6rem !important;
        }
      }
      
      /* 超小屏幕优化 */
      @media (max-width: 360px) {
        [data-testid="metric-container"] [data-testid="metric-value"] {
          font-size: 1rem !important;
        }
        [data-testid="metric-container"] [data-testid="metric-label"] {
          font-size: 0.7rem !important;
        }
        [data-testid="metric-container"] [data-testid="metric-delta"] {
          font-size: 0.6rem !important;
        }
        
        /* 自定义metrics超小屏幕优化 */
        .metric-row {
          gap: 0.2rem !important;
        }
        .metric-item {
          padding: 0.5rem !important;
        }
        .metric-value {
          font-size: 1rem !important;
        }
        .metric-label {
          font-size: 0.6rem !important;
        }
        .metric-delta {
          font-size: 0.5rem !important;
        }
      }
      </style>
    """,
    unsafe_allow_html=True,
)

# 侧边栏控制（暂时注释掉，后续需要时再启用）
# st.sidebar.header('控制')
# interval = st.sidebar.slider('刷新间隔(秒)', min_value=10, max_value=120, value=30, step=5)
# auto_refresh = st.sidebar.checkbox('自动刷新', value=True)

# 固定配置参数
interval = 30  # 固定30秒刷新间隔
auto_refresh = True  # 固定开启自动刷新

# 读取配置与基线
try:
    cfg = pc.load_config()
    monitor_cfg = cfg.get('monitor', {})
    threshold = float(monitor_cfg.get('alert_threshold_percent', 2.0))
    baseline_file = monitor_cfg.get('baseline_file') or os.path.join(os.path.dirname(__file__), '进度基准_1分钟_截止0510.csv')
    baseline = pc.load_baseline(baseline_file)

    # 加载分类基准数据
    category_baseline_file = os.path.join(os.path.dirname(__file__), "分类进度基准_1分钟_截止0510.csv")
    try:
        category_baseline = pc.load_category_baseline(category_baseline_file)
    except FileNotFoundError:
        category_baseline = None
        st.warning(f"分类基准文件未找到: {category_baseline_file}")

    # 控制数据获取和终端输出频率
    should_fetch_data = False
    should_print = False
    
    if 'last_refresh_time' not in st.session_state:
        st.session_state.last_refresh_time = datetime.now()
        should_fetch_data = True
        should_print = True
    else:
        # 检查是否需要刷新（超过设定间隔）
        time_diff = (datetime.now() - st.session_state.last_refresh_time).total_seconds()
        if time_diff >= interval:
            st.session_state.last_refresh_time = datetime.now()
            should_fetch_data = True
            should_print = True
    
    # 只在需要时获取新数据
    if should_fetch_data or 'cached_stats' not in st.session_state:
        session = requests.Session()
        stats, meta = pc.fetch_progress(cfg['api'], debug=False, session=session)
        result = pc.compare_with_baseline(stats, baseline, threshold)
        
        # 缓存数据
        st.session_state.cached_stats = stats
        st.session_state.cached_result = result
        st.session_state.cached_meta = meta
    else:
        # 使用缓存的数据
        stats = st.session_state.cached_stats
        result = st.session_state.cached_result
        meta = st.session_state.cached_meta

    # 统一的终端输出逻辑
    if should_print:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n[{current_time}] 数据刷新 📊")
        print(f"  总任务数: {stats.get('total_tasks', 0)}")
        print(f"  已完成: {stats.get('completed_tasks', 0)}")
        print(f"  实际完成率: {result.get('actual_order_pct', 0.0):.1f}%")
        print(f"  目标完成率: {result.get('required_order_pct', 0.0):.1f}%")
        print(f"  状态: {result.get('status', 'UNKNOWN')}")
        print(f"  差值: {result.get('delta_pct', 0.0):+.1f}%")
except Exception as e:
    st.error('看板加载失败，请检查接口与基线配置。')
    st.stop()

actual_pct = float(result.get('actual_order_pct', 0.0))
required_pct = float(result.get('required_order_pct', 0.0))
delta_pct = float(result.get('delta_pct', actual_pct - required_pct))

# 响应式状态和鼓励语句布局
# 在移动端垂直排列，桌面端水平排列
status_col, encourage_display_col = st.columns([1, 1])
with status_col:
    status = result.get('status', 'UNKNOWN')
    status_class = 'status-ok' if status == 'OK' else ('status-warn' if status == 'WARN' else 'status-unknown')
    st.markdown(f"<span class='status-pill {status_class}'>状态：{status}</span>", unsafe_allow_html=True)

with encourage_display_col:
    # 显示动态鼓励内容（移动端居中，桌面端右对齐）
    encouragement = get_encouragement_message(delta_pct, status, actual_pct)
    st.markdown(f"""
    <div style='text-align: right; font-size: 14px; color: #666; margin-top: 5px;'>
        <span style='display: inline-block; text-align: center; width: 100%;'>{encouragement}</span>
    </div>
    """, unsafe_allow_html=True)

# 响应式数据指标布局 - 优化手机端显示
# 使用自定义HTML布局替代Streamlit的metric组件以获得更好的移动端体验
st.markdown("""
<div class="metrics-container">
    <div class="metric-row">
        <div class="metric-item">
            <div class="metric-value">{}</div>
            <div class="metric-label">总任务数</div>
        </div>
        <div class="metric-item">
            <div class="metric-value">{}</div>
            <div class="metric-label">已完成</div>
        </div>
    </div>
    <div class="metric-row">
        <div class="metric-item">
            <div class="metric-value">{}%</div>
            <div class="metric-label">目标比例</div>
        </div>
        <div class="metric-item">
            <div class="metric-value">{}%</div>
            <div class="metric-label">实际比例</div>
            <div class="metric-delta">{:+.1f}% 相对目标</div>
        </div>
    </div>
</div>
""".format(
    stats.get('total_tasks', 0),
    stats.get('completed_tasks', 0), 
    required_pct,
    actual_pct,
    delta_pct
), unsafe_allow_html=True)

# 红蓝双线紧贴对比（HTML/CSS 实现）

# 规范化百分比范围
_target = max(0.0, min(100.0, required_pct))
_actual = max(0.0, min(100.0, actual_pct))

chart_html = f"""
<style>
.cmp-box {{ border:1px solid #e5e7eb; border-radius:12px; padding:14px; background:#ffffff; }}
.cmp-stack {{ position:relative; width:100%; height:26px; border-radius:10px; background:#f3f4f6; }}
.cmp-line {{ position:absolute; left:0; height:10px; border-radius:6px; }}
.cmp-line.target {{ top:3px; background:#ef4444; }}
.cmp-line.actual {{ top:13px; background:#3b82f6; }}
.cmp-legend {{ display:flex; justify-content:flex-end; margin-top:6px; font-size:12px; }}
.cmp-legend-item {{ margin-left:15px; }}
.cmp-legend-item.target {{ color:#ef4444; }}
.cmp-legend-item.actual {{ color:#3b82f6; }}
</style>
<div class='cmp-box'>
  <div class='cmp-stack'>
    <div class='cmp-line target' style='width:{_target}%;'></div>
    <div class='cmp-line actual' style='width:{_actual}%;'></div>
  </div>
  <div class='cmp-legend'>
    <span class='cmp-legend-item target'>目标: {_target:.1f}%</span>
    <span class='cmp-legend-item actual'>实际: {_actual:.1f}%</span>
  </div>
</div>
"""

st.markdown(chart_html, unsafe_allow_html=True)

# 添加分类进度标题和间隔
st.markdown("---")
st.markdown("### 分类进度")
st.markdown("")  # 添加空行间隔

# 获取分类进度数据
try:
    # 只在需要时获取新的分类数据
    if should_fetch_data or 'cached_categories' not in st.session_state:
        categories, cat_meta = pc.fetch_category_progress(cfg['api'], debug=False)
        
        # 缓存分类数据
        st.session_state.cached_categories = categories
        st.session_state.cached_cat_meta = cat_meta
    else:
        # 使用缓存的分类数据
        categories = st.session_state.cached_categories
        cat_meta = st.session_state.cached_cat_meta
    
    # 只在首次加载或达到刷新间隔时输出分类数据信息
    if should_print:
        if categories:
            print(f"  分类数据: {len(categories)}个分类")
            for cat in categories:
                rate = cat.get('completion_rate', 0.0)
                finished = cat.get('finished_count', 0)
                total = cat.get('total_count', 0)
                print(f"    {cat.get('name', 'Unknown')}: {rate:.1f}% ({finished}/{total})")
        else:
            print("  分类数据: 无数据")
    
    if categories:
        # 如果有分类基准数据，进行对比
        if category_baseline is not None:
            current_time = datetime.now()
            comparison_result = pc.compare_categories_with_baseline(
                categories, category_baseline, current_time
            )
            
            # 使用对比结果更新分类数据
            if comparison_result['status'] != 'NO_BASELINE':
                for i, cat in enumerate(categories):
                    for comp_cat in comparison_result['categories']:
                        if cat['name'] == comp_cat['name']:
                            categories[i].update({
                                'baseline_rate': comp_cat['baseline_rate'],
                                'delta': comp_cat['delta'],
                                'comparison_status': comp_cat['status']
                            })
                            break
        
        # 使用自定义HTML布局替代5列布局，确保在手机端单行显示
        for cat in categories:
            with st.container():
                # 创建分类卡片 - 使用自定义HTML确保单行显示
                st.markdown(f"""
                <div class="category-card">
                    <div class="category-header">{cat['name']}</div>
                    <div class="category-metrics">
                        <div class="category-metric">
                            <div class="metric-value">{cat['total_count']}</div>
                            <div class="metric-label">总任务数</div>
                        </div>
                        <div class="category-metric">
                            <div class="metric-value">{cat['finished_count']}</div>
                            <div class="metric-label">已完成</div>
                        </div>
                        <div class="category-metric">
                            <div class="metric-value">{cat['unfinished_count']}</div>
                            <div class="metric-label">未完成</div>
                        </div>
                        <div class="category-metric">
                            <div class="metric-value">{cat.get('baseline_rate', cat['completion_rate']):.1f}%</div>
                            <div class="metric-label">{'目标比例' if 'baseline_rate' in cat and cat.get('baseline_rate') is not None else '完成率'}</div>
                        </div>
                        <div class="category-metric">
                            <div class="metric-value">{cat['completion_rate']:.1f}%</div>
                            <div class="metric-label">实际比例</div>
                            {f'<div class="metric-delta">{cat.get("delta", 0):+.1f}% 相对目标</div>' if 'baseline_rate' in cat and cat.get('baseline_rate') is not None else ''}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 使用与总体进度相同的红蓝双线对比样式
                if 'baseline_rate' in cat and cat.get('baseline_rate') is not None:
                    baseline_rate = cat['baseline_rate']
                    actual_rate = cat['completion_rate']
                    
                    # 规范化百分比范围
                    _baseline = max(0.0, min(100.0, baseline_rate))
                    _actual = max(0.0, min(100.0, actual_rate))
                    
                    # 使用相同的HTML/CSS样式，但移除delta显示
                    category_chart_html = f"""
                    <style>
                    .cat-cmp-box {{ border:1px solid #e5e7eb; border-radius:12px; padding:14px; background:#ffffff; margin:10px 0; }}
                    .cat-cmp-stack {{ position:relative; width:100%; height:26px; border-radius:10px; background:#f3f4f6; }}
                    .cat-cmp-line {{ position:absolute; left:0; height:10px; border-radius:6px; }}
                    .cat-cmp-line.target {{ top:3px; background:#ef4444; }}
                    .cat-cmp-line.actual {{ top:13px; background:#3b82f6; }}
                    .cat-cmp-legend {{ display:flex; justify-content:flex-end; margin-top:6px; font-size:12px; }}
                    .cat-cmp-legend-item {{ margin-left:15px; }}
                    .cat-cmp-legend-item.target {{ color:#ef4444; }}
                    .cat-cmp-legend-item.actual {{ color:#3b82f6; }}
                    </style>
                    <div class='cat-cmp-box'>
                      <div class='cat-cmp-stack'>
                        <div class='cat-cmp-line target' style='width:{_baseline}%;'></div>
                        <div class='cat-cmp-line actual' style='width:{_actual}%;'></div>
                      </div>
                      <div class='cat-cmp-legend'>
                        <span class='cat-cmp-legend-item target'>目标: {_baseline:.1f}%</span>
                        <span class='cat-cmp-legend-item actual'>实际: {_actual:.1f}%</span>
                      </div>
                    </div>
                    """
                    
                    st.markdown(category_chart_html, unsafe_allow_html=True)
                else:
                    # 如果没有基准数据，显示简单的进度条（使用相同样式）
                    actual_rate = cat['completion_rate']
                    _actual = max(0.0, min(100.0, actual_rate))
                    
                    simple_chart_html = f"""
                    <style>
                    .cat-simple-box {{ border:1px solid #e5e7eb; border-radius:12px; padding:14px; background:#ffffff; margin:10px 0; }}
                    .cat-simple-stack {{ position:relative; width:100%; height:16px; border-radius:8px; background:#f3f4f6; }}
                    .cat-simple-line {{ position:absolute; left:0; top:0; height:16px; border-radius:8px; background:#3b82f6; }}
                    .cat-simple-legend {{ margin-top:6px; font-size:12px; color:#6b7280; text-align:center; }}
                    </style>
                    <div class='cat-simple-box'>
                      <div class='cat-simple-stack'>
                        <div class='cat-simple-line' style='width:{_actual}%;'></div>
                      </div>
                      <div class='cat-simple-legend'>完成进度: {_actual:.1f}%</div>
                    </div>
                    """
                    
                    st.markdown(simple_chart_html, unsafe_allow_html=True)
                
                st.markdown("---")  # 分隔线
    else:
        st.warning("无法获取分类数据")
        
except Exception as e:
    st.error(f"获取分类数据失败: {str(e)}")
    categories = []

# 在页面最后显示分类进度详情表格
if 'categories' in locals() and categories:
    st.subheader("📊 分类进度详情")
    
    # 创建DataFrame用于表格显示
    df_data = []
    for cat in categories:
        row = {
            '分类名称': cat['name'],
            '完成率': f"{cat['completion_rate']:.1f}%",
            '已完成': cat['finished_count'],
            '未完成': cat['unfinished_count'],
            '总计': cat['total_count']
        }
        
        # 如果有基准对比数据，添加对比列
        if 'baseline_rate' in cat:
            row['目标率'] = f"{cat['baseline_rate']:.1f}%"
            row['差值'] = f"{cat['delta']:+.1f}%"
            
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    
    # 显示表格
    st.dataframe(
        df,
        width='stretch',
        hide_index=True
    )



# 在页面底部添加自动刷新功能
if auto_refresh:
    # 检查是否需要刷新（与终端输出逻辑保持一致）
    if 'last_refresh_time' not in st.session_state:
        # 首次加载，直接刷新
        time.sleep(interval)
        st.rerun()
    else:
        # 检查距离上次刷新的时间
        time_since_last_refresh = (datetime.now() - st.session_state.last_refresh_time).total_seconds()
        remaining_time = interval - time_since_last_refresh
        
        if remaining_time <= 0:
            # 时间已到，立即刷新
            st.rerun()
        else:
            # 等待剩余时间后刷新
            time.sleep(remaining_time)
            st.rerun()
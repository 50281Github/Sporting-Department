import os
import csv
import json
import math
import sys
import time
from datetime import datetime
from typing import Dict, Any, Tuple

import requests
import argparse
import pandas as pd


def load_config() -> Dict[str, Any]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, '..', 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def floor_to_5_min(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    floored_minute = dt.minute - (dt.minute % 5)
    return f"{dt.hour:02d}:{floored_minute:02d}"

def get_time_key(baseline: Dict[str, Dict[str, float]], dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    exact = f"{dt.hour:02d}:{dt.minute:02d}"
    if exact in baseline:
        return exact
    # 若基线不包含精确分钟，则回退到5分钟取整
    return floor_to_5_min(dt)


def _resolve_baseline_path(csv_path: str) -> str:
    """将配置中的基线路径解析为实际存在的文件路径。
    优先尝试脚本目录，其次尝试上级目录（项目根）。
    """
    if not csv_path:
        raise FileNotFoundError("未配置基线CSV路径")
    if os.path.isabs(csv_path):
        return csv_path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, csv_path),
        os.path.join(script_dir, '..', csv_path),
    ]
    for p in candidates:
        if os.path.exists(p):
            return os.path.abspath(p)
    # 最后再尝试当前工作目录
    cwd_path = os.path.abspath(os.path.join(os.getcwd(), csv_path))
    if os.path.exists(cwd_path):
        return cwd_path
    # 都不存在则抛错，便于用户修正配置
    raise FileNotFoundError(f"未找到进度基准CSV: {candidates[0]}")


def load_category_baseline(baseline_file: str) -> pd.DataFrame:
    """加载分类基准数据"""
    if not os.path.exists(baseline_file):
        raise FileNotFoundError(f'分类基准文件不存在: {baseline_file}')
    
    df = pd.read_csv(baseline_file, encoding='utf-8')
    
    # 确保时间列格式正确
    if '时间' in df.columns:
        df['时间'] = pd.to_datetime(df['时间'], format='%H:%M').dt.time
    
    return df


def compare_categories_with_baseline(categories: list, category_baseline: pd.DataFrame, current_time: datetime, threshold: float = 2.0) -> Dict[str, Any]:
    """将分类进度与基准对比"""
    current_time_obj = current_time.time()
    
    # 查找最接近的基准时间点
    baseline_row = None
    min_diff = float('inf')
    
    for _, row in category_baseline.iterrows():
        baseline_time = row['时间']
        if isinstance(baseline_time, str):
            baseline_time = datetime.strptime(baseline_time, '%H:%M').time()
        
        # 计算时间差（以分钟为单位）
        current_minutes = current_time_obj.hour * 60 + current_time_obj.minute
        baseline_minutes = baseline_time.hour * 60 + baseline_time.minute
        
        # 处理跨天情况 - 修复逻辑
        # 如果当前时间在18:00-23:59之间，而基准时间在00:00-17:59之间，说明基准时间是第二天
        if current_time_obj.hour >= 18 and baseline_time.hour < 18:
            baseline_minutes += 24 * 60  # 基准时间加一天
        # 如果当前时间在00:00-17:59之间，而基准时间在18:00-23:59之间，说明基准时间是前一天
        elif current_time_obj.hour < 18 and baseline_time.hour >= 18:
            baseline_minutes -= 24 * 60  # 基准时间减一天
        
        diff = abs(current_minutes - baseline_minutes)
        if diff < min_diff:
            min_diff = diff
            baseline_row = row
    
    if baseline_row is None:
        return {'status': 'NO_BASELINE', 'categories': []}
    
    # 对比各分类
    category_comparisons = []
    overall_status = 'OK'
    
    for category in categories:
        cat_name = category['name']
        actual_rate = category['completion_rate']
        
        # 查找对应的基准列
        baseline_rate = 0.0
        for col in category_baseline.columns:
            if col != '时间' and cat_name in col:
                baseline_rate = float(baseline_row[col]) if pd.notna(baseline_row[col]) else 0.0
                break
        
        # 计算差值
        delta = actual_rate - baseline_rate
        
        # 判断状态
        status = 'OK'
        if delta < -threshold:
            status = 'WARN'
            overall_status = 'WARN'
        elif delta < -threshold * 2:
            status = 'CRITICAL'
            overall_status = 'CRITICAL'
        
        category_comparisons.append({
            'name': cat_name,
            'actual_rate': actual_rate,
            'baseline_rate': baseline_rate,
            'delta': delta,
            'status': status,
            'total_count': category['total_count'],
            'finished_count': category['finished_count'],
            'unfinished_count': category['unfinished_count']
        })
    
    return {
        'status': overall_status,
        'baseline_time': baseline_row['时间'],
        'current_time': current_time_obj.strftime('%H:%M'),
        'categories': category_comparisons,
        'threshold': threshold
    }


def load_baseline(csv_path: str) -> Dict[str, Dict[str, float]]:
    mapping: Dict[str, Dict[str, float]] = {}
    csv_path = _resolve_baseline_path(csv_path)
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get('时间') or row.get('time') or '').strip()
            if not t:
                continue
            def to_float(val):
                try:
                    return float(str(val).strip())
                except Exception:
                    return 0.0
            mapping[t] = {
                'order_pct': to_float(row.get('累计单数完成比例(%)') or row.get('order_pct')),
                'weight_pct': to_float(row.get('累计重量完成比例(%)') or row.get('weight_pct'))
            }
    return mapping


def fetch_category_progress(api_cfg: Dict[str, Any], debug: bool = False, session: requests.Session | None = None) -> Tuple[list, Dict[str, Any]]:
    """获取分类进度数据"""
    url = api_cfg['base_url'].rstrip('/') + '/' + api_cfg['endpoint'].lstrip('/')
    headers = api_cfg.get('headers', {})
    # 获取目标日期，逻辑：每天18:00后自动切换到次日数据
    now = datetime.now()
    if now.hour >= 18:
        # 18点后，请求次日数据
        from datetime import timedelta
        target_date = (now + timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
    else:
        # 18点前，请求当天数据
        target_date = now.strftime('%Y-%m-%d 00:00:00')
    
    params = {
        'time_config_id': api_cfg.get('time_config_id'),
        'target_date': target_date
    }
    s = session or requests
    resp = s.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    
    # 提取分类进度数据
    categories = []
    payload = data.get('data') or {}
    category_schedule = payload.get('category_schedule', [])
    
    for category in category_schedule:
        categories.append({
            'id': category.get('id', ''),
            'name': category.get('name', ''),
            'total_count': category.get('total_count', 0),
            'finished_count': category.get('finished_count', 0),
            'unfinished_count': category.get('unfinished_count', 0),
            'out_of_stock_count': category.get('out_of_stock_count', 0),
            'completion_rate': round((category.get('finished_count', 0) / category.get('total_count', 1)) * 100, 1) if category.get('total_count', 0) > 0 else 0.0
        })
    
    meta = {
        'http_status': resp.status_code,
        'api_status': data.get('code'),
        'api_msg': data.get('msg') or data.get('message'),
        'total_categories': len(categories)
    }
    
    if debug:
        print("分类数据调试信息:")
        print(f"- HTTP状态: {meta['http_status']}")
        print(f"- API状态: {meta['api_status']} | 提示: {meta['api_msg']}")
        print(f"- 分类数量: {meta['total_categories']}")
        for cat in categories[:3]:  # 只显示前3个分类
            print(f"- {cat['name']}: {cat['finished_count']}/{cat['total_count']} ({cat['completion_rate']}%)")
    
    return categories, meta


def fetch_progress(api_cfg: Dict[str, Any], debug: bool = False, session: requests.Session | None = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    url = api_cfg['base_url'].rstrip('/') + '/' + api_cfg['endpoint'].lstrip('/')
    headers = api_cfg.get('headers', {})
    # 获取目标日期，逻辑：每天18:00后自动切换到次日数据
    now = datetime.now()
    if now.hour >= 18:
        # 18点后，请求次日数据
        from datetime import timedelta
        target_date = (now + timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
    else:
        # 18点前，请求当天数据
        target_date = now.strftime('%Y-%m-%d 00:00:00')
    
    params = {
        'time_config_id': api_cfg.get('time_config_id'),
        # 该接口需要 target_date，格式示例：2000-01-01 00:00:00
        'target_date': target_date
    }
    s = session or requests
    resp = s.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # 容错解析统计信息
    stats = {
        'total_tasks': 0,
        'completed_tasks': 0
    }
    payload = data.get('data') or {}
    # 常见结构：data.statistics 或 data.weight_info.statistics
    statistics = (
        payload.get('statistics')
        or (payload.get('weight_info') or {}).get('statistics')
        or {}
    )
    # 映射可能字段名
    candidates_total = [
        'total_tasks', 'task_total', 'total', 'total_task_count', 'sum_task'
    ]
    candidates_done = [
        'completed_tasks', 'finished', 'done', 'finished_count', 'completed'
    ]
    for key in candidates_total:
        if statistics.get(key) is not None:
            stats['total_tasks'] = statistics.get(key)
            break
    for key in candidates_done:
        if statistics.get(key) is not None:
            stats['completed_tasks'] = statistics.get(key)
            break
    # 可能存在的结构1: payload['statistics'] = {'total_tasks': x, 'completed_tasks': y}
    st = payload.get('statistics') or {}
    stats['total_tasks'] = stats['total_tasks'] or st.get('total_tasks') or st.get('task_total') or st.get('total') or 0
    stats['completed_tasks'] = stats['completed_tasks'] or st.get('completed_tasks') or st.get('finished') or st.get('done') or 0
    # 结构2: 从任务列表推断
    if stats['total_tasks'] == 0 and isinstance(payload.get('tasks'), list):
        tasks = payload['tasks']
        stats['total_tasks'] = len(tasks)
        stats['completed_tasks'] = sum(1 for t in tasks if str(t.get('status')).lower() in ['finished', 'done', 'completed'])
    # 结构2.1：API返回 total_schedule（从调试输出来看存在该结构）
    if stats['total_tasks'] == 0 and isinstance(payload.get('total_schedule'), dict):
        ts = payload['total_schedule']
        stats['total_tasks'] = ts.get('total_count', 0)
        stats['completed_tasks'] = ts.get('finished_count', 0)
    # 结构3: 其他可能字段
    stats['total_tasks'] = stats['total_tasks'] or payload.get('total_tasks') or payload.get('task_total') or 0
    stats['completed_tasks'] = stats['completed_tasks'] or payload.get('completed_tasks') or payload.get('finished') or 0
    meta = {
        'http_status': resp.status_code,
        'api_status': data.get('status'),
        'api_msg': data.get('msg') or data.get('message'),
    }
    if debug:
        # 打印部分关键字段，帮助诊断请求头/权限问题
        print("接口调试信息:")
        print(f"- HTTP状态: {meta['http_status']}")
        print(f"- API状态: {meta['api_status']} | 提示: {meta['api_msg']}")
        print(f"- 顶层键: {list(data.keys())[:10]}")
        print(f"- data键: {list((data.get('data') or {}).keys())[:10]}")
        # 若统计为空，打印一个片段供参考
        if stats['total_tasks'] == 0:
            snippet = json.dumps((data.get('data') or {}), ensure_ascii=False)[:300]
            print(f"- data片段: {snippet}...\n")
    return stats, meta


def compare_with_baseline(stats: Dict[str, Any], baseline: Dict[str, Dict[str, float]], threshold: float = 2.0) -> Dict[str, Any]:
    time_key = get_time_key(baseline)
    target = baseline.get(time_key)
    
    # 如果找不到对应的基准数据，尝试使用最接近的数据
    if not target and baseline:
        from datetime import datetime
        current_time = datetime.now()
        current_minutes = current_time.hour * 60 + current_time.minute
        
        # 找到最接近的时间点
        closest_key = None
        min_diff = float('inf')
        
        for key in baseline.keys():
            try:
                hour, minute = map(int, key.split(':'))
                key_minutes = hour * 60 + minute
                diff = abs(current_minutes - key_minutes)
                
                # 处理跨天的情况（如凌晨时间与前一天晚上的时间比较）
                if diff > 12 * 60:  # 如果差值超过12小时，考虑跨天
                    diff = min(diff, 24 * 60 - diff)
                
                if diff < min_diff:
                    min_diff = diff
                    closest_key = key
            except ValueError:
                continue
        
        if closest_key:
            target = baseline.get(closest_key)
            time_key = closest_key
    
    actual_order_pct = round((stats.get('completed_tasks', 0) / stats.get('total_tasks', 0)) * 100, 1) if stats.get('total_tasks', 0) > 0 else 0.0
    required_order_pct = float(target.get('order_pct', 0.0)) if target else 0.0
    delta = round(actual_order_pct - required_order_pct, 1)
    status = 'OK' if target and actual_order_pct >= required_order_pct - threshold else ('NO_BASELINE' if not target else 'WARN')
    return {
        'time_point': time_key,
        'actual_order_pct': actual_order_pct,
        'required_order_pct': required_order_pct,
        'delta_pct': delta,
        'status': status
    }


def main():
    try:
        parser = argparse.ArgumentParser(description='即时进度比对（不落盘）')
        parser.add_argument('--debug', action='store_true', help='打印接口调试信息')
        parser.add_argument('--watch', action='store_true', help='持续运行并定期刷新比对')
        parser.add_argument('--interval-seconds', type=int, default=30, help='刷新间隔秒数（默认30）')
        args = parser.parse_args()

        cfg = load_config()
        monitor_cfg = cfg.get('monitor', {})
        baseline_file = monitor_cfg.get('baseline_file') or '进度基准_5分钟_截止0510.csv'
        threshold = float(monitor_cfg.get('alert_threshold_percent', 2.0))

        baseline = load_baseline(baseline_file)

        def run_once(session: requests.Session | None = None) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
            stats, meta = fetch_progress(cfg['api'], debug=args.debug, session=session)
            result = compare_with_baseline(stats, baseline, threshold)
            print("==== 分拣进度即时比对（不落盘）====")
            print(f"HTTP: {meta.get('http_status')} | API状态: {meta.get('api_status')} | 提示: {meta.get('api_msg')}")
            print(f"当前时间点: {result['time_point']}")
            print(f"总任务数: {stats.get('total_tasks', 0)} | 已完成: {stats.get('completed_tasks', 0)}")
            print(f"目标完成比例(单数): {result['required_order_pct']}%")
            print(f"实际完成比例(单数): {result['actual_order_pct']}%")
            print(f"与目标差值: {result['delta_pct']}%")
            print(f"状态: {result['status']}")
            return result, stats, meta

        if args.watch:
            print(f"已开启持续模式，每 {args.interval_seconds} 秒刷新一次。按 Ctrl+C 停止。\n")
            session = requests.Session()
            try:
                while True:
                    try:
                        os.system('cls' if os.name == 'nt' else 'clear')
                    except Exception:
                        pass
                    run_once(session=session)
                    time.sleep(max(1, int(args.interval_seconds)))
            except KeyboardInterrupt:
                print("已停止持续模式。")
                sys.exit(0)
        else:
            result, stats, meta = run_once()
            # 以退出码提示是否达标：0=OK/NO_BASELINE, 1=WARN
            if result['status'] == 'WARN':
                sys.exit(1)
            else:
                sys.exit(0)
    except Exception as e:
        print(f"运行失败: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()
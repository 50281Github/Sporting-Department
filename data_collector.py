#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
现场部-分拣进度数据采集器
定时从观麦业务平台API获取分拣数据并保存
"""

import requests
import json
import csv
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import schedule

class DataCollector:
    def __init__(self, config_file='config.json'):
        """初始化数据采集器"""
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.session = requests.Session()
        self.setup_session()
        
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "api": {
                "base_url": "https://station.guanmai.cn",
                "endpoint": "/weight/weight_collect/weight_info/get",
                "time_config_id": "ST22071",
                "headers": {
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Host": "station.guanmai.cn",
                    "Pragma": "no-cache",
                    "Referer": "https://station.guanmai.cn/",
                    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "X-Guanmai-Request-Id": "1735462800000-1735462800000"
                }
            },
            "collection": {
                "interval_minutes": 5,
                "data_dir": "collected_data",
                "csv_filename": "sorting_progress_{date}.csv",
                "json_filename": "sorting_progress_{date}.json",
                "log_filename": "collector.log"
            },
            "retry": {
                "max_attempts": 3,
                "delay_seconds": 5
            }
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # 合并配置
                    default_config.update(user_config)
            except Exception as e:
                print(f"配置文件加载失败，使用默认配置: {e}")
        
        return default_config
    
    def setup_logging(self):
        """设置日志记录"""
        log_dir = self.config['collection']['data_dir']
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, self.config['collection']['log_filename'])
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_session(self):
        """设置请求会话"""
        self.session.headers.update(self.config['api']['headers'])
    
    def get_target_date(self, offset_days: int = 0) -> str:
        """获取目标日期字符串
        
        逻辑：每天18:00后自动切换到次日数据
        - 18:00之前：请求当天数据
        - 18:00之后：请求次日数据
        """
        now = datetime.now()
        
        # 判断是否已过18点
        if now.hour >= 18:
            # 18点后，请求次日数据
            target_date = now + timedelta(days=1 + offset_days)
            self.logger.info(f"当前时间 {now.strftime('%H:%M')} 已过18点，请求次日数据: {target_date.strftime('%Y-%m-%d')}")
        else:
            # 18点前，请求当天数据
            target_date = now + timedelta(days=offset_days)
            self.logger.info(f"当前时间 {now.strftime('%H:%M')} 未过18点，请求当天数据: {target_date.strftime('%Y-%m-%d')}")
        
        return target_date.strftime('%Y-%m-%d 00:00:00')
    
    def fetch_data(self, target_date: str = None) -> Dict[str, Any]:
        """从API获取数据"""
        if target_date is None:
            target_date = self.get_target_date()

        url = f"{self.config['api']['base_url']}{self.config['api']['endpoint']}"
        params = {
            'time_config_id': self.config['api']['time_config_id'],
            'target_date': target_date
        }

        for attempt in range(self.config['retry']['max_attempts']):
            try:
                self.logger.info(f"正在获取数据 (尝试 {attempt + 1}/{self.config['retry']['max_attempts']})")
                self.logger.info(f"请求URL: {url}")
                self.logger.info(f"请求参数: {params}")

                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()
                self.logger.info(f"数据获取成功，响应大小: {len(response.text)} 字符")
                return {
                    'timestamp': datetime.now().isoformat(),
                    'target_date': target_date,
                    'data': data,
                    'status': 'success'
                }

            except requests.exceptions.RequestException as e:
                self.logger.error(f"请求失败 (尝试 {attempt + 1}): {e}")
                if attempt < self.config['retry']['max_attempts'] - 1:
                    time.sleep(self.config['retry']['delay_seconds'])
                else:
                    return {
                        'timestamp': datetime.now().isoformat(),
                        'target_date': target_date,
                        'error': str(e),
                        'status': 'failed'
                    }
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析失败: {e}")
                return {
                    'timestamp': datetime.now().isoformat(),
                    'target_date': target_date,
                    'error': f"JSON解析失败: {e}",
                    'status': 'failed'
                }
    
    def fetch_sorter_rank_data(self, cycle_start_time: str = None, cycle_end_time: str = None) -> Dict[str, Any]:
        """获取分拣员排名数据
        
        逻辑：与分拣进度数据保持一致，18:00后自动切换到次日数据
        """
        if cycle_start_time is None or cycle_end_time is None:
            now = datetime.now()
            
            # 判断是否已过18点，决定查询哪一天的数据
            if now.hour >= 18:
                # 18点后，查询次日的5:00-9:00数据
                target_date = (now + timedelta(days=1)).strftime('%Y-%m-%d')
                self.logger.info(f"当前时间 {now.strftime('%H:%M')} 已过18点，查询次日分拣员排名数据: {target_date}")
            else:
                # 18点前，查询当天的5:00-9:00数据
                target_date = now.strftime('%Y-%m-%d')
                self.logger.info(f"当前时间 {now.strftime('%H:%M')} 未过18点，查询当天分拣员排名数据: {target_date}")
            
            cycle_start_time = f"{target_date} 05:00"
            cycle_end_time = f"{target_date} 09:00"

        url = f"{self.config['api']['base_url']}/weight/weight_collect/sorter/rank"
        params = {
            'time_config_id': self.config['api']['time_config_id'],
            'cycle_start_time': cycle_start_time,
            'cycle_end_time': cycle_end_time
        }

        for attempt in range(self.config['retry']['max_attempts']):
            try:
                self.logger.info(f"正在获取分拣员排名数据 (尝试 {attempt + 1}/{self.config['retry']['max_attempts']})")
                self.logger.info(f"请求URL: {url}")
                self.logger.info(f"请求参数: {params}")

                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()
                self.logger.info(f"分拣员排名数据获取成功，响应大小: {len(response.text)} 字符")
                
                # 统计排名数据
                if data.get('code') == 0 and isinstance(data.get('data'), list):
                    sorter_count = len(data['data'])
                    total_results = sum(item.get('statistic_results', 0) for item in data['data'])
                    self.logger.info(f"获取到 {sorter_count} 名分拣员排名数据，总计完成 {total_results} 件")
                
                return {
                    'timestamp': datetime.now().isoformat(),
                    'cycle_start_time': cycle_start_time,
                    'cycle_end_time': cycle_end_time,
                    'data': data,
                    'status': 'success'
                }

            except requests.exceptions.RequestException as e:
                self.logger.error(f"分拣员排名数据请求失败 (尝试 {attempt + 1}): {e}")
                if attempt < self.config['retry']['max_attempts'] - 1:
                    time.sleep(self.config['retry']['delay_seconds'])
                else:
                    return {
                        'timestamp': datetime.now().isoformat(),
                        'cycle_start_time': cycle_start_time,
                        'cycle_end_time': cycle_end_time,
                        'error': str(e),
                        'status': 'failed'
                    }
            except json.JSONDecodeError as e:
                self.logger.error(f"分拣员排名数据JSON解析失败: {e}")
                return {
                    'timestamp': datetime.now().isoformat(),
                    'cycle_start_time': cycle_start_time,
                    'cycle_end_time': cycle_end_time,
                    'error': f"JSON解析失败: {e}",
                    'status': 'failed'
                }
    
    def save_sorter_rank_to_json(self, data: Dict[str, Any], date_str: str = None):
        """保存分拣员排名数据到JSON文件"""
        data_dir = self.config['collection']['data_dir']
        os.makedirs(data_dir, exist_ok=True)
        
        filename = "sorter_rank.json"
        filepath = os.path.join(data_dir, filename)
        
        # 如果文件存在，追加到数组中
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
                existing_data.append(data)
            except:
                existing_data = [data]
        else:
            existing_data = [data]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"分拣员排名数据已保存到JSON文件: {filepath}")
    
    def save_sorter_rank_to_csv(self, data: Dict[str, Any], date_str: str = None):
        """保存分拣员排名数据到CSV文件"""
        data_dir = self.config['collection']['data_dir']
        os.makedirs(data_dir, exist_ok=True)
        
        # 保存分拣员排名详细数据
        detail_filename = "sorter_rank_detail.csv"
        detail_filepath = os.path.join(data_dir, detail_filename)
        
        # 保存分拣员排名汇总数据
        summary_filename = "sorter_rank_summary.csv"
        summary_filepath = os.path.join(data_dir, summary_filename)
        
        # 检查文件是否存在，决定是否写入表头
        detail_file_exists = os.path.exists(detail_filepath)
        summary_file_exists = os.path.exists(summary_filepath)
        
        try:
            # 保存详细数据记录
            with open(detail_filepath, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 如果文件不存在，写入表头
                if not detail_file_exists:
                    headers = [
                        '采集时间', '周期开始时间', '周期结束时间', 'API状态码', 'API消息',
                        '分拣员姓名', '排名', '完成件数', '响应状态', '备注'
                    ]
                    writer.writerow(headers)
                
                # 写入详细数据行
                api_data = data.get('data', {})
                if api_data.get('code') == 0 and isinstance(api_data.get('data'), list):
                    for sorter in api_data['data']:
                        row = [
                            data['timestamp'],
                            data['cycle_start_time'],
                            data['cycle_end_time'],
                            api_data.get('code', ''),
                            api_data.get('msg', ''),
                            sorter.get('sorter_name', ''),
                            sorter.get('rank', ''),
                            sorter.get('statistic_results', ''),
                            data['status'],
                            ''
                        ]
                        writer.writerow(row)
                else:
                    # 如果API返回错误或无数据，记录错误信息
                    row = [
                        data['timestamp'],
                        data['cycle_start_time'],
                        data['cycle_end_time'],
                        api_data.get('code', ''),
                        api_data.get('msg', ''),
                        '',
                        '',
                        '',
                        data['status'],
                        data.get('error', '')
                    ]
                    writer.writerow(row)
            
            # 保存汇总统计数据
            with open(summary_filepath, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 如果文件不存在，写入表头
                if not summary_file_exists:
                    headers = [
                        '采集时间', '周期开始时间', '周期结束时间', 
                        '分拣员总数', '总完成件数', '平均完成件数', '响应状态'
                    ]
                    writer.writerow(headers)
                
                # 计算汇总统计
                api_data = data.get('data', {})
                if api_data.get('code') == 0 and isinstance(api_data.get('data'), list):
                    sorter_count = len(api_data['data'])
                    total_results = sum(item.get('statistic_results', 0) for item in api_data['data'])
                    avg_results = total_results / sorter_count if sorter_count > 0 else 0
                else:
                    sorter_count = 0
                    total_results = 0
                    avg_results = 0
                
                row = [
                    data['timestamp'],
                    data['cycle_start_time'],
                    data['cycle_end_time'],
                    sorter_count,
                    total_results,
                    round(avg_results, 2),
                    data['status']
                ]
                writer.writerow(row)
            
            self.logger.info(f"分拣员排名数据已保存到CSV文件: {detail_filepath} 和 {summary_filepath}")
            
        except Exception as e:
            self.logger.error(f"保存分拣员排名CSV数据时出错: {e}")
    
    def save_to_json(self, data: Dict[str, Any], date_str: str = None):
        """保存数据到JSON文件"""
        data_dir = self.config['collection']['data_dir']
        os.makedirs(data_dir, exist_ok=True)
        
        filename = self.config['collection']['json_filename'].format(date=date_str)
        filepath = os.path.join(data_dir, filename)
        
        # 如果文件存在，追加到数组中
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
                existing_data.append(data)
            except:
                existing_data = [data]
        else:
            existing_data = [data]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"数据已保存到JSON文件: {filepath}")
    
    def save_to_csv(self, data: Dict[str, Any], date_str: str = None):
        """保存数据到CSV文件"""
        data_dir = self.config['collection']['data_dir']
        os.makedirs(data_dir, exist_ok=True)
        
        # 保存原始数据记录
        raw_filename = "raw_data.csv"
        raw_filepath = os.path.join(data_dir, raw_filename)
        
        # 保存统计汇总数据
        summary_filename = "summary_stats.csv"
        summary_filepath = os.path.join(data_dir, summary_filename)
        
        # 检查文件是否存在，决定是否写入表头
        raw_file_exists = os.path.exists(raw_filepath)
        summary_file_exists = os.path.exists(summary_filepath)
        
        try:
            # 保存原始数据记录
            with open(raw_filepath, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 如果文件不存在，写入表头
                if not raw_file_exists:
                    headers = [
                        '采集时间', '目标日期', 'API状态码', 'API消息', 
                        '响应状态', '原始数据', '备注'
                    ]
                    writer.writerow(headers)
                
                # 写入原始数据行
                api_data = data.get('data', {})
                row = [
                    data['timestamp'],
                    data['target_date'],
                    api_data.get('code', ''),
                    api_data.get('msg', ''),
                    data['status'],
                    json.dumps(api_data, ensure_ascii=False),
                    data.get('error', '')
                ]
                writer.writerow(row)
            
            # 如果API返回成功且有数据，尝试解析统计信息
            if data['status'] == 'success' and isinstance(api_data, dict) and api_data.get('code') == 0:
                api_response_data = api_data.get('data')
                
                # 根据您提供的图片，设计统计数据表头
                with open(summary_filepath, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    
                    # 如果文件不存在，写入统计表头
                    if not summary_file_exists:
                        summary_headers = [
                            '采集时间', '目标日期',
                            '总任务数', '已完成任务数', '缺货任务数', '未完成任务数',
                            '计重任务数', '商品种类数', '不计重任务数', '商户数',
                            # 分类进度统计（基于API返回的真实分类）
                            '新鲜蔬菜_未完成', '新鲜蔬菜_已完成', '新鲜蔬菜_缺货',
                            '新鲜肉类_未完成', '新鲜肉类_已完成', '新鲜肉类_缺货',
                            '鲜活水产_未完成', '鲜活水产_已完成', '鲜活水产_缺货',
                            '时令果蔬_未完成', '时令果蔬_已完成', '时令果蔬_缺货',
                            '鲜活禽类_未完成', '鲜活禽类_已完成', '鲜活禽类_缺货',
                            '休闲食品_未完成', '休闲食品_已完成', '休闲食品_缺货',
                            '速冻速食_未完成', '速冻速食_已完成', '速冻速食_缺货',
                            '南北干货_未完成', '南北干货_已完成', '南北干货_缺货',
                            '厨房酱料_未完成', '厨房酱料_已完成', '厨房酱料_缺货',
                            '乳品烘焙_未完成', '乳品烘焙_已完成', '乳品烘焙_缺货',
                            '厨房用品_未完成', '厨房用品_已完成', '厨房用品_缺货',
                            '米面粮油_未完成', '米面粮油_已完成', '米面粮油_缺货',
                            '腊味熟食_未完成', '腊味熟食_已完成', '腊味熟食_缺货',
                            '其他_未完成', '其他_已完成', '其他_缺货',
                            # 其他统计字段
                            '总重量(kg)', '平均重量(kg)', 'API响应时间(ms)', '数据完整性'
                        ]
                        writer.writerow(summary_headers)
                    
                    # 解析并写入统计数据
                    if api_response_data and isinstance(api_response_data, dict):
                        # 从API响应中提取统计数据，传入完整的API数据
                        stats = self.parse_statistics(api_data)
                        
                        summary_row = [
                            data['timestamp'],
                            data['target_date'],
                            stats.get('total_tasks', 0),
                            stats.get('completed_tasks', 0),
                            stats.get('shortage_tasks', 0),
                            stats.get('uncompleted_tasks', 0),
                            stats.get('weight_tasks', 0),
                            stats.get('product_types', 0),
                            stats.get('no_weight_tasks', 0),
                            stats.get('merchant_count', 0),
                            # 分类统计数据（按照新的表头顺序）
                            stats.get('新鲜蔬菜_未完成', 0), stats.get('新鲜蔬菜_已完成', 0), stats.get('新鲜蔬菜_缺货', 0),
                            stats.get('新鲜肉类_未完成', 0), stats.get('新鲜肉类_已完成', 0), stats.get('新鲜肉类_缺货', 0),
                            stats.get('鲜活水产_未完成', 0), stats.get('鲜活水产_已完成', 0), stats.get('鲜活水产_缺货', 0),
                            stats.get('时令果蔬_未完成', 0), stats.get('时令果蔬_已完成', 0), stats.get('时令果蔬_缺货', 0),
                            stats.get('鲜活禽类_未完成', 0), stats.get('鲜活禽类_已完成', 0), stats.get('鲜活禽类_缺货', 0),
                            stats.get('休闲食品_未完成', 0), stats.get('休闲食品_已完成', 0), stats.get('休闲食品_缺货', 0),
                            stats.get('速冻速食_未完成', 0), stats.get('速冻速食_已完成', 0), stats.get('速冻速食_缺货', 0),
                            stats.get('南北干货_未完成', 0), stats.get('南北干货_已完成', 0), stats.get('南北干货_缺货', 0),
                            stats.get('厨房酱料_未完成', 0), stats.get('厨房酱料_已完成', 0), stats.get('厨房酱料_缺货', 0),
                            stats.get('乳品烘焙_未完成', 0), stats.get('乳品烘焙_已完成', 0), stats.get('乳品烘焙_缺货', 0),
                            stats.get('厨房用品_未完成', 0), stats.get('厨房用品_已完成', 0), stats.get('厨房用品_缺货', 0),
                            stats.get('米面粮油_未完成', 0), stats.get('米面粮油_已完成', 0), stats.get('米面粮油_缺货', 0),
                            stats.get('腊味熟食_未完成', 0), stats.get('腊味熟食_已完成', 0), stats.get('腊味熟食_缺货', 0),
                            stats.get('其他_未完成', 0), stats.get('其他_已完成', 0), stats.get('其他_缺货', 0),
                            # 其他统计
                            stats.get('total_weight', 0),
                            stats.get('avg_weight', 0),
                            stats.get('response_time', 0),
                            stats.get('data_integrity', '完整')
                        ]
                        writer.writerow(summary_row)
                    else:
                        # 如果没有有效数据，写入空行或错误信息
                        empty_row = [data['timestamp'], data['target_date']] + [''] * (len(summary_headers) - 2)
                        writer.writerow(empty_row)
            
            self.logger.info(f"数据已保存到CSV文件: {raw_filepath}")
            if data['status'] == 'success':
                self.logger.info(f"统计数据已保存到: {summary_filepath}")
            
        except Exception as e:
            self.logger.error(f"保存CSV文件失败: {e}")
    
    def parse_statistics(self, api_data: Dict[str, Any]) -> Dict[str, Any]:
        """解析API响应数据，提取统计信息"""
        stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'shortage_tasks': 0,
            'uncompleted_tasks': 0,
            'weight_tasks': 0,
            'product_types': 0,
            'no_weight_tasks': 0,
            'merchant_count': 0,
            'total_weight': 0,
            'avg_weight': 0,
            'response_time': 0,
            'data_integrity': '完整'
        }
        
        try:
            # 根据真实API响应结构解析数据
            if 'data' in api_data and api_data['data']:
                data = api_data['data']
                
                # 解析分类调度数据 (category_schedule)
                if 'category_schedule' in data and isinstance(data['category_schedule'], list):
                    category_data = data['category_schedule']
                    
                    for category in category_data:
                        category_id = category.get('id', '')
                        total_count = category.get('total_count', 0)
                        finished_count = category.get('finished_count', 0)
                        unfinished_count = category.get('unfinished_count', 0)
                        out_of_stock_count = category.get('out_of_stock_count', 0)
                        
                        # 映射分类ID到中文名称（使用API返回的name字段）
                        category_name = category.get('name', '其他')
                         
                        # 如果没有name字段，使用ID映射
                        if not category_name or category_name == '其他':
                            category_name_map = {
                                'A627108': '新鲜蔬菜',
                                'A627109': '新鲜肉类', 
                                'A627111': '鲜活水产',
                                'A627113': '时令果蔬',
                                'A627110': '鲜活禽类',
                                'A627118': '休闲食品',
                                'A627112': '速冻速食',
                                'A627115': '南北干货',
                                'A627119': '厨房酱料',
                                'A627114': '乳品烘焙',
                                'A629184': '厨房用品',
                                'A627117': '米面粮油',
                                'A627116': '腊味熟食'
                            }
                            category_name = category_name_map.get(category_id, '其他')
                        
                        # 设置分类统计
                        stats[f'{category_name}_未完成'] = unfinished_count
                        stats[f'{category_name}_已完成'] = finished_count
                        stats[f'{category_name}_缺货'] = out_of_stock_count
                        
                        # 累计总数
                        stats['total_tasks'] += total_count
                        stats['completed_tasks'] += finished_count
                        stats['uncompleted_tasks'] += unfinished_count
                        stats['shortage_tasks'] += out_of_stock_count
                
                # 解析排序数据 (sort_data)
                if 'sort_data' in data:
                    sort_data = data['sort_data']
                    stats['merchant_count'] = sort_data.get('address_count', 0)
                    stats['product_types'] = sort_data.get('sku_count', 0)
                    stats['no_weight_tasks'] = sort_data.get('unweight_count', 0)
                    stats['weight_tasks'] = sort_data.get('weight_count', 0)
                
                # 解析总调度数据 (total_schedule)
                if 'total_schedule' in data:
                    total_schedule = data['total_schedule']
                    # 验证总数是否一致
                    api_total = total_schedule.get('total_count', 0)
                    api_finished = total_schedule.get('finished_count', 0)
                    api_unfinished = total_schedule.get('unfinished_count', 0)
                    api_out_of_stock = total_schedule.get('out_of_stock_count', 0)
                    
                    # 使用API提供的总数（更准确）
                    if api_total > 0:
                        stats['total_tasks'] = api_total
                        stats['completed_tasks'] = api_finished
                        stats['uncompleted_tasks'] = api_unfinished
                        stats['shortage_tasks'] = api_out_of_stock
                
                # 计算平均重量（如果有重量数据）
                if stats['weight_tasks'] > 0 and stats['total_weight'] > 0:
                    stats['avg_weight'] = round(stats['total_weight'] / stats['weight_tasks'], 2)
                
                self.logger.info(f"成功解析统计数据: 总任务{stats['total_tasks']}, 已完成{stats['completed_tasks']}, 未完成{stats['uncompleted_tasks']}, 缺货{stats['shortage_tasks']}")
            
        except Exception as e:
            self.logger.error(f"解析统计数据失败: {e}")
            stats['data_integrity'] = f'解析错误: {str(e)}'
        
        return stats
    
    def collect_once(self):
        """执行一次数据采集"""
        self.logger.info("=" * 60)
        self.logger.info("开始执行数据采集...")
        self.logger.info(f"采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 获取分拣进度数据
        data = self.fetch_data()
        
        # 保存分拣进度数据
        date_str = datetime.now().strftime('%Y%m%d')
        self.save_to_json(data, date_str)
        self.save_to_csv(data, date_str)
        
        if data['status'] == 'success':
            # 解析并显示分拣进度详细信息
            stats = self.parse_statistics(data.get('data', {}))
            self.logger.info("✓ 分拣进度数据采集完成")
            self.logger.info(f"  📊 总任务数: {stats.get('total_tasks', 0)}")
            self.logger.info(f"  ✅ 已完成: {stats.get('completed_tasks', 0)}")
            self.logger.info(f"  ⏳ 未完成: {stats.get('uncompleted_tasks', 0)}")
            self.logger.info(f"  ❌ 缺货: {stats.get('shortage_tasks', 0)}")
            
            # 计算并显示完成率
            if stats.get('total_tasks', 0) > 0:
                completion_rate = round((stats.get('completed_tasks', 0) / stats.get('total_tasks', 0)) * 100, 1)
                self.logger.info(f"  📈 完成率: {completion_rate}%")
            
            # 显示商户和商品信息
            if stats.get('merchant_count', 0) > 0:
                self.logger.info(f"  🏪 商户数: {stats.get('merchant_count', 0)}")
            if stats.get('product_types', 0) > 0:
                self.logger.info(f"  📦 商品种类: {stats.get('product_types', 0)}")
            
            # 显示计重信息
            weight_tasks = stats.get('weight_tasks', 0)
            no_weight_tasks = stats.get('no_weight_tasks', 0)
            if weight_tasks > 0 or no_weight_tasks > 0:
                self.logger.info(f"  ⚖️ 计重任务: {weight_tasks} | 不计重任务: {no_weight_tasks}")
        else:
            self.logger.error(f"✗ 分拣进度数据采集失败: {data.get('error', '未知错误')}")
        
        self.logger.info("")  # 空行分隔
        
        # 获取分拣员排名数据
        self.logger.info("开始获取分拣员排名数据...")
        sorter_rank_data = self.fetch_sorter_rank_data()
        
        # 保存分拣员排名数据
        self.save_sorter_rank_to_json(sorter_rank_data, date_str)
        self.save_sorter_rank_to_csv(sorter_rank_data, date_str)
        
        if sorter_rank_data['status'] == 'success':
            # 显示分拣员排名详细信息
            api_data = sorter_rank_data.get('data', {})
            if api_data.get('code') == 0 and isinstance(api_data.get('data'), list):
                sorters = api_data['data']
                total_completed = sum(sorter.get('statistic_results', 0) for sorter in sorters)
                self.logger.info("✓ 分拣员排名数据采集完成")
                self.logger.info(f"  👥 分拣员总数: {len(sorters)}")
                self.logger.info(f"  📦 总完成件数: {total_completed}")
                if sorters:
                    avg_completed = round(total_completed / len(sorters), 1) if len(sorters) > 0 else 0
                    self.logger.info(f"  📊 平均完成件数: {avg_completed}")
                    # 显示前3名分拣员
                    top_sorters = sorted(sorters, key=lambda x: x.get('statistic_results', 0), reverse=True)[:3]
                    self.logger.info("  🏆 排名前三:")
                    for i, sorter in enumerate(top_sorters, 1):
                        self.logger.info(f"    {i}. {sorter.get('sorter_name', '未知')} - {sorter.get('statistic_results', 0)}件")
        else:
            self.logger.error(f"✗ 分拣员排名数据采集失败: {sorter_rank_data.get('error', '未知错误')}")
        
        # 采集完成总结
        self.logger.info("")  # 空行分隔
        overall_status = 'success' if data['status'] == 'success' and sorter_rank_data['status'] == 'success' else 'partial_success'
        if overall_status == 'success':
            self.logger.info("🎉 本次数据采集全部完成!")
        else:
            self.logger.info("⚠️ 本次数据采集部分完成")
        
        self.logger.info("=" * 60)
        self.logger.info("")  # 最后的空行分隔
        
        return {
            'sorting_progress': data,
            'sorter_ranking': sorter_rank_data,
            'status': overall_status,
            'timestamp': datetime.now().isoformat()
        }
    
    def start_scheduled_collection(self):
        """启动定时采集"""
        interval = self.config['collection']['interval_minutes']
        self.logger.info(f"启动定时数据采集，间隔: {interval} 分钟")
        
        # 立即执行一次
        self.collect_once()
        
        # 设置定时任务
        schedule.every(interval).minutes.do(self.collect_once)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("收到停止信号，正在退出...")
        except Exception as e:
            self.logger.error(f"定时任务执行出错: {e}")

def main():
    """主函数"""
    import sys
    
    print("现场部-分拣进度数据采集器")
    print("=" * 50)
    
    collector = DataCollector()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            print("\n执行测试模式 - 单次数据采集...")
            result = collector.collect_once()
            print(f"采集结果: {result['status']}")
            if result['status'] == 'success':
                print("✓ 数据采集成功")
            else:
                print(f"✗ 数据采集失败: {result.get('error', '未知错误')}")
            return
        elif sys.argv[1] == 'schedule':
            print(f"\n启动定时采集 (间隔: {collector.config['collection']['interval_minutes']} 分钟)")
            print("按 Ctrl+C 停止采集")
            collector.start_scheduled_collection()
            return
    
    print("选择运行模式:")
    print("1. 执行一次采集")
    print("2. 启动定时采集")
    print("3. 直接启动定时采集（默认）")
    print()
    print("提示：直接按回车将启动定时采集模式")
    
    try:
        choice = input("请输入选择 (1/2 或直接回车): ").strip()
        
        if choice == '1':
            print("\n执行单次数据采集...")
            result = collector.collect_once()
            print(f"采集结果: {result['status']}")
            if result['status'] == 'success':
                print("✓ 数据采集成功")
            else:
                print(f"✗ 数据采集失败: {result.get('error', '未知错误')}")
            
        elif choice == '2' or choice == '' or choice == '3':
            print(f"\n启动定时采集 (间隔: {collector.config['collection']['interval_minutes']} 分钟)")
            print("按 Ctrl+C 停止采集")
            collector.start_scheduled_collection()
            
        else:
            print("无效选择，默认启动定时采集...")
            print(f"\n启动定时采集 (间隔: {collector.config['collection']['interval_minutes']} 分钟)")
            print("按 Ctrl+C 停止采集")
            collector.start_scheduled_collection()
            
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"程序执行出错: {e}")

if __name__ == "__main__":
    main()
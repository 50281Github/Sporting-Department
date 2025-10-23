# 现场部-分拣进度记录系统

一个用于采集、存储和展示现场部分拣进度数据的完整解决方案，集成观麦业务平台API接口，支持分拣进度监控和分拣员排名统计。

## 系统组成

### 1. 数据采集器 (data_collector.py)
- **双重数据抓取**: 同时采集分拣进度数据和分拣员排名数据
- **自动定时采集**: 每5分钟自动从观麦业务平台API获取最新数据
- **多格式存储**: 支持保存为CSV和JSON格式，便于不同用途的数据分析
- **错误处理**: 完善的重试机制和日志记录
- **灵活配置**: 可调整采集间隔、存储路径等参数

### 2. Web展示系统
- **实时数据展示**: 统计总重量、订单数、完成进度等关键指标
- **详细记录表格**: 展示订单号、商品名称、重量、状态等信息
- **可视化图表**: 分拣进度分布的饼图展示
- **数据筛选**: 支持按日期、订单号、商品名称、状态筛选

## 数据采集功能

### 核心特性
- **双重数据源**: 
  - 分拣进度数据：任务完成情况、重量统计等
  - 分拣员排名数据：个人工作效率、排名统计等
- **定时采集**: 按配置的时间间隔自动获取数据（默认5分钟）
- **实时存储**: 数据实时保存到本地文件
- **断点续传**: 支持程序重启后继续采集
- **数据备份**: 同时保存JSON和CSV格式，确保数据安全

### 采集配置
- **采集间隔**: 默认5分钟，可在config.json中调整
- **存储路径**: collected_data目录
- **文件命名**: 按日期和数据类型自动命名，便于管理
- **日志记录**: 详细的操作日志，便于问题排查

### 数据文件说明

采集的数据会保存在 `collected_data` 目录下：

#### 分拣进度数据
- **JSON文件**: `sorting_progress_YYYYMMDD.json` - 保留完整的API响应数据
- **详细CSV**: `raw_data_YYYYMMDD.csv` - 原始数据记录
- **汇总CSV**: `summary_stats_YYYYMMDD.csv` - 统计汇总数据

#### 分拣员排名数据
- **JSON文件**: `sorter_rank_YYYYMMDD.json` - 保留完整的排名数据
- **详细CSV**: `sorter_rank_detail_YYYYMMDD.csv` - 每个分拣员的详细信息
- **汇总CSV**: `sorter_rank_summary_YYYYMMDD.csv` - 团队统计汇总

#### 系统日志
- **日志文件**: `collector.log` - 记录采集过程和错误信息

## 技术架构

### 前端技术
- **HTML5**: 语义化页面结构
- **CSS3**: 现代化样式设计，支持响应式布局
- **JavaScript ES6+**: 原生JavaScript实现，无框架依赖
- **Chart.js**: 数据可视化图表库
- **Font Awesome**: 图标库

### 后端服务
- **Node.js**: 运行环境
- **Express**: Web服务器框架
- **http-proxy-middleware**: API代理中间件
- **CORS**: 跨域资源共享支持

### 数据采集
- **Python 3**: 数据采集脚本运行环境
- **Requests**: HTTP请求库
- **Schedule**: 定时任务调度
- **JSON/CSV**: 多格式数据存储

### API集成
- **观麦业务平台API**: 获取分拣数据和排名数据
- **代理服务器**: 解决跨域访问问题
- **错误处理**: 提供降级方案和模拟数据

## 快速开始

### 数据采集器使用

#### 方法一：使用启动脚本（推荐）

**Windows批处理脚本:**
```bash
# 双击运行
start_scheduler.bat
```

**PowerShell脚本:**
```bash
# 右键 -> 使用PowerShell运行
start_scheduler.ps1
```

#### 方法二：命令行运行
```bash
# 安装Python依赖
pip install -r requirements.txt

# 启动定时采集（推荐）
python data_collector.py schedule

# 或执行一次采集
python data_collector.py once
```

### 配置说明

编辑 `config.json` 文件可以调整以下参数：

```json
{
  "collection": {
    "interval_minutes": 5,        // 采集间隔（分钟）
    "data_dir": "collected_data", // 数据存储目录
    "csv_filename": "sorting_progress_{date}.csv",  // CSV文件名格式
    "json_filename": "sorting_progress_{date}.json" // JSON文件名格式
  },
  "api": {
    "base_url": "https://station.guanmai.cn",
    "endpoint": "/weight/weight_collect/weight_info/get",
    "time_config_id": "ST22071",
    "headers": {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    },
    "cookie": "your_cookie_here"
  },
  "retry": {
    "max_attempts": 3,    // 最大重试次数
    "delay_seconds": 5    // 重试间隔（秒）
  }
}
```

### Web展示系统使用

#### 独立版本（无需Node.js）
直接在浏览器中打开 `standalone.html` 文件

#### 完整版本（需要Node.js）
```bash
# 安装依赖
npm install

# 启动服务器
npm start

# 访问 http://localhost:3000
```

## 项目结构

```
现场部-分拣进度记录/
├── data_collector.py       # 数据采集器主程序
├── config.json            # 配置文件
├── requirements.txt       # Python依赖
├── start_scheduler.bat    # Windows启动脚本
├── start_scheduler.ps1    # PowerShell启动脚本
├── run_collector.bat      # 旧版启动脚本（兼容）
├── collected_data/        # 数据存储目录
│   ├── sorting_progress_*.json    # 分拣进度JSON数据
│   ├── raw_data_*.csv            # 分拣进度详细CSV
│   ├── summary_stats_*.csv       # 分拣进度汇总CSV
│   ├── sorter_rank_*.json        # 分拣员排名JSON数据
│   ├── sorter_rank_detail_*.csv  # 分拣员排名详细CSV
│   ├── sorter_rank_summary_*.csv # 分拣员排名汇总CSV
│   └── collector.log             # 系统日志
├── index.html             # Web展示主页面
├── styles.css             # 样式文件
├── script.js              # 前端逻辑
├── proxy-server.js        # 代理服务器
├── package.json           # 项目配置
└── README.md             # 项目文档
```

## API接口

### 1. 获取分拣进度数据
```
GET /weight/weight_collect/weight_info/get
```

**参数:**
- `time_config_id`: 时间配置ID (默认: ST22071)
- `target_date`: 目标日期 (格式: YYYY-MM-DD+05:00)

### 2. 获取分拣员排名数据
```
GET /weight/weight_collect/sorter/rank
```

**参数:**
- `time_config_id`: 时间配置ID (默认: ST22071)
- `cycle_start_time`: 周期开始时间 (格式: YYYY-MM-DD HH:MM)
- `cycle_end_time`: 周期结束时间 (格式: YYYY-MM-DD HH:MM)

**响应示例:**
```json
{
  "code": 0,
  "msg": "ok",
  "data": [
    {
      "sorter_name": "张三",
      "rank": 1,
      "statistic_results": 150
    }
  ]
}
```

## 数据分析功能

### 分拣进度统计
- 总任务数量
- 已完成任务数
- 未完成任务数
- 缺货任务数
- 完成率计算

### 分拣员效率分析
- 个人完成件数排名
- 团队平均效率
- 工作时段分析
- 效率趋势统计

### 数据导出
- CSV格式便于Excel分析
- JSON格式保留完整数据结构
- 按日期自动分类存储
- 支持历史数据查询

## 使用说明

### 启动数据采集
1. **首次使用**: 确保已安装Python 3.7+和相关依赖
2. **配置API**: 在config.json中设置正确的cookie和配置参数
3. **启动采集**: 运行启动脚本或命令行启动
4. **监控日志**: 查看collected_data/collector.log了解运行状态

### 停止数据采集
- 在运行窗口按 `Ctrl+C` 停止
- 或直接关闭命令行窗口

### 查看采集数据
- **实时监控**: 查看日志文件了解采集状态
- **数据分析**: 打开CSV文件进行数据分析
- **历史查询**: 按日期查找对应的数据文件

## 故障排除

### 常见问题

1. **无法获取数据**
   - 检查网络连接
   - 确认cookie是否有效
   - 查看collector.log中的错误信息

2. **Python环境问题**
   - 确保Python版本3.7+
   - 安装依赖: `pip install -r requirements.txt`
   - 检查虚拟环境配置

3. **权限问题**
   - 确保对collected_data目录有写入权限
   - 以管理员身份运行（如需要）

4. **API接口问题**
   - 检查time_config_id是否正确
   - 确认API接口地址未变更
   - 验证请求参数格式

### 日志分析
系统会记录详细的运行日志，包括:
- 数据采集成功/失败记录
- API请求和响应信息
- 错误详情和重试记录
- 数据保存状态

## 开发指南

### 添加新的数据源
1. 在DataCollector类中添加新的fetch方法
2. 实现对应的数据保存方法
3. 在collect_once方法中集成新数据源
4. 更新配置文件和文档

### 自定义数据处理
1. 修改parse_statistics方法处理新的数据格式
2. 调整CSV输出格式和字段
3. 添加新的统计指标计算

### 扩展Web展示
1. 在script.js中添加新的数据处理逻辑
2. 在index.html中添加对应的UI元素
3. 在styles.css中添加样式

## 版本历史

### v2.0.0 (2025-09-29)
- 新增分拣员排名数据采集功能
- 支持双重数据源同步采集
- 优化数据存储结构和文件命名
- 改进启动脚本和用户体验
- 完善错误处理和日志记录

### v1.0.0 (2025-01-28)
- 初始版本发布
- 基础分拣进度数据采集
- Web展示系统
- API集成和代理服务器
- 响应式用户界面

## 许可证

MIT License

## 支持

如有问题或建议，请联系现场部开发团队。
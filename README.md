# 天猫电商大数据商业分析与智能助手平台

基于 **Flask + Vanna + DeepSeek** 的电商数据分析平台：深色主题数据大屏（ECharts）+ 中文自然语言智能助手（自动生成 SQL、去重、过滤配件误判并输出商品链接）。

## 目录结构

```
D:\TmallDataAI Assistant\
├── .env                # 敏感配置 (DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL)
├── .gitignore
├── config.py           # 全局常量与配置
├── vanna_core.py       # Vanna 初始化、DeepSeek 注入、知识库训练
├── web_app.py          # Flask 路由、登录鉴权、看板查询、问答接口
├── run.py              # 启动入口
├── load_data.py        # 数据清洗、商品去重、入库
├── tmall.db            # SQLite 数据库（load_data.py 生成）
├── TmallData.csv       # 原始数据（也支持 TmallData/ 目录）
├── templates/
│   ├── base.html       # 导航栏 + Tailwind 深色主题 + 页脚
│   ├── dashboard.html  # 数据看板
│   └── assistant.html  # 智能助手
└── README.md
```

## 快速开始

```powershell
# 1. 安装依赖（如未安装）
.\.venv\Scripts\python.exe -m pip install flask vanna openai python-dotenv pandas numpy

# 2. 数据入库（去重后约 1.1 万条商品）
.\.venv\Scripts\python.exe load_data.py

# 3. 启动
.\.venv\Scripts\python.exe run.py
```

访问 <http://127.0.0.1:5000>，演示账号 **admin / 123456**。

> 数据库为空或不存在时，启动过程会自动执行入库。

## 页面

| 路由 | 内容 |
| --- | --- |
| `/dashboard` | 商品总数、品牌数、总销量、平均价格；热销商品 TOP10、发货地分布、一级类目分布 |
| `/assistant` | 自然语言问答，返回中文结论 + 商品链接，可展开查看 SQL |
| `/vanna` | Vanna 原生界面 |
| `/login` `/logout` | 登录 / 退出 |

## 数据质量处理

- **商品去重**：`load_data.py` 按 `商品ID` 去重（保留最新采集），并再次按 `商品标题 + 店铺名称` 去重；问答结果在 `web_app.py` 中二次去重。
- **配件误判**：知识库中明确「按品类推荐必须用 `二级类目名称` 过滤，如 `二级类目名称 = '手机'`，禁止只用标题 LIKE」；同时 `filter_accessory_results()` 会在问「手机」时剔除标题含 膜/壳/保护套/充电/数据线/支架 等配件词的结果。
- **数值化**：`年销量`（7000+、1.8万+）及价格、佣金、补贴等列统一转为数值，空值为 NULL。

## 智能问答接口

`POST /api/ask`

```json
{ "question": "推荐手机" }
```

返回 `answer`（中文结论 + 商品链接）、`sql`、`row_count`。

## 说明

DeepSeek 不提供 embeddings 接口，且离线环境无法下载 ONNX 模型，因此向量库使用内置 `HashEmbeddingFunction`（字符 n-gram 哈希，384 维）完成本地召回。知识库已有训练数据时自动跳过训练。

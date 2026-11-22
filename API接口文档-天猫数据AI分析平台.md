# 天猫数据 AI 分析平台 API 接口文档

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v1.0 |
| 编写日期 | 2026-11-15 |
| 适用系统 | 基于大语言模型的天猫电商大数据分析与智能助手系统 |
| 对应代码 | `web_app.py`（路由）、`config.py`（配置） |
| 服务地址 | `http://127.0.0.1:5000` |
| 目标读者 | 测试人员、前后端联调人员 |
终端输入：.\.venv\Scripts\python.exe run.py 开启系统

---

## 1 文档说明

### 1.1 编写目的

本文档描述系统对外暴露的全部 HTTP 接口，包括页面路由与 JSON 数据接口，供测试人员设计用例、执行回归与定位问题。文档中的路径、参数、状态码与返回字段均以当前代码实现为准。

### 1.2 服务启动

```powershell
cd "d:\TmallDataAI Assistant"
.venv\Scripts\python.exe run.py
```

服务默认监听 `0.0.0.0:5000`，本机访问 `http://127.0.0.1:5000`。首次启动或数据库缺失时，系统会自动执行 `load_data.py` 完成入库；也可手动执行：

```powershell
.venv\Scripts\python.exe load_data.py
```

### 1.3 协议与数据格式

- 传输协议：HTTP/1.1
- 页面路由：返回 `text/html`（Jinja2 渲染）或 `302` 重定向
- 数据接口：返回 `application/json; charset=utf-8`
- 表单接口：`application/x-www-form-urlencoded` 或 `multipart/form-data`
- JSON 接口：`application/json`

### 1.4 认证机制

系统采用 **Flask Session + Cookie** 认证，不使用 Token。

1. 调用 `POST /login` 提交用户名与密码；
2. 登录成功后服务端在 Session 中写入 `logged_in=true`、`username`、`role`；
3. 浏览器自动保存 `session` Cookie，后续请求携带该 Cookie；
4. 使用脚本测试时，必须保持 Cookie 会话（`curl -c` / `-b`，或 `requests.Session()`）。

登录成功后会话字段：

| Session 键 | 类型 | 说明 |
| --- | --- | --- |
| `logged_in` | bool | 是否已登录 |
| `username` | string | 当前用户名 |
| `user` | string | 与 `username` 相同，兼容旧代码 |
| `role` | string | `admin` 或 `user` |
| `chat_sid` | string | 会话标识，首次问答或查询历史时生成 |

> 说明：所有账号（含 `admin`）均走数据库校验，不存在硬编码后门。默认演示账号为 `admin / 123456`，若数据库中的密码已被修改，以实际密码为准。

### 1.5 统一响应约定

**（1）页面路由。** 返回 HTML 或 302 重定向。校验失败时通常返回 200 并在页面中展示错误文案，而不是返回 4xx。测试时应同时检查 HTTP 状态码、`Location` 响应头与页面关键文案。

**（2）JSON 接口。** 统一包含布尔字段 `ok`：

```json
{ "ok": true }
```

失败时：

```json
{ "ok": false, "error": "错误描述" }
```

### 1.6 通用状态码

| 状态码 | 含义 | 典型场景 |
| --- | --- | --- |
| 200 | 成功 | 页面渲染、登录失败、查询成功 |
| 302 | 重定向 | 登录成功、未登录访问页面、无权限访问页面、后台操作完成 |
| 400 | 参数错误 | `/api/ask` 问题为空、无法识别凑单品类 |
| 401 | 未登录 | 未登录调用 `/api/*` |
| 403 | 无权限 | 非管理员调用 `/api/admin/*` |
| 500 | 服务端错误 | 模型调用失败、SQL 执行失败、方案生成失败 |

---

## 2 权限矩阵

系统通过全局 `before_request` 拦截器统一鉴权。公开路径为：`/login`、`/logout`、`/register`、`/forget_password`、`/static/*`、`/assets/*`、`/favicon.ico`、`/vanna.svg`、`/auth/*`。

| 路径 | 未登录 | 普通用户 `user` | 管理员 `admin` |
| --- | --- | --- | --- |
| `/login`、`/register`、`/forget_password` | 允许 | 允许 | 允许 |
| `/logout` | 允许 | 允许 | 允许 |
| `/home`、`/assistant`、`/profile` | 302 → `/login` | 允许 | 允许 |
| `/api/history`、`/api/ask` | 401 JSON | 允许 | 允许 |
| `/dashboard` | 302 → `/login` | 302 → `/home?denied=1` | 允许 |
| `/admin`、`/admin/users/toggle` | 302 → `/login` | 302 → `/home?denied=1` | 允许 |
| `/api/admin/*`（预留前缀） | 401 JSON | 403 JSON | 允许 |
| `/`、`/vanna`、其他路径 | 302 → `/login` | 由 Vanna SPA 处理 | 由 Vanna SPA 处理 |

---

## 3 接口总览

| 编号 | 方法 | 路径 | 功能 | 权限 | 返回类型 |
| --- | --- | --- | --- | --- | --- |
| A1 | GET | `/login` | 登录页 | 公开 | HTML |
| A2 | POST | `/login` | 提交登录 | 公开 | 302 / HTML |
| A3 | GET | `/register` | 注册页 | 公开 | HTML |
| A4 | POST | `/register` | 提交注册 | 公开 | 302 / HTML |
| A5 | GET | `/forget_password` | 找回密码页 | 公开 | HTML |
| A6 | POST | `/forget_password` | 重置密码 | 公开 | 302 / HTML |
| A7 | GET | `/logout` | 退出登录 | 公开 | 302 |
| A8 | GET | `/profile` | 个人中心页 | 登录 | HTML |
| A9 | POST | `/profile` | 修改资料/密码 | 登录 | HTML |
| B1 | GET | `/home` | 商品首页与筛选 | 登录 | HTML |
| B2 | GET | `/dashboard` | 数据看板 | 管理员 | HTML |
| B3 | GET | `/assistant` | 智能助手页 | 登录 | HTML |
| B4 | GET | `/admin` | 系统后台 | 管理员 | HTML |
| C1 | GET | `/api/history` | 查询会话历史 | 登录 | JSON |
| C2 | DELETE | `/api/history` | 清空会话历史 | 登录 | JSON |
| C3 | POST | `/api/ask` | 智能问答/凑单 | 登录 | JSON |
| C4 | POST | `/admin/users/toggle` | 封禁/解封用户 | 管理员 | 302 |
| D1 | GET | `/` | 根路径跳转 | 登录 | 302 |
| D2 | GET | `/vanna`、`/vanna/*`、其他路径 | Vanna 原生 SPA | 登录 | HTML |

---

## 4 认证与账号接口

### 4.1 A1/A2 登录

- **路径**：`/login`
- **方法**：GET（渲染页面）、POST（提交登录）
- **权限**：公开
- **请求格式**：表单

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 用户名，自动去除首尾空格 |
| `password` | string | 是 | 密码 |

请求示例：

```bash
curl.exe -i -c cookies.txt -X POST http://127.0.0.1:5000/login \
  -d "username=admin" -d "password=123456"
```

成功响应：

```
HTTP/1.1 302 FOUND
Location: /home
Set-Cookie: session=...
```

失败响应（HTTP 200，页面展示错误）：

| 场景 | 页面文案 |
| --- | --- |
| 用户不存在或密码错误 | `账号或密码错误` |
| 账号被管理员封禁 | `该账号已被封禁，请联系管理员` |

测试要点：

1. 密码错误、用户名为空、密码为空均应停留在登录页；
2. 登录成功后 Session 中 `role` 必须与数据库一致；
3. 已登录用户再次访问 `/login` 仍展示登录页，不会强制跳转；
4. 管理员与普通用户走同一校验逻辑，不存在 `admin/123456` 特殊通道。

### 4.2 A3/A4 注册

- **路径**：`/register`
- **方法**：GET、POST
- **权限**：公开
- **请求格式**：表单

请求参数：

| 参数 | 类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `username` | string | 是 | 3～20 个字符，唯一 |
| `password` | string | 是 | 不少于 6 位 |
| `confirm_password` | string | 是 | 必须与 `password` 一致 |
| `email` | string | 否 | 若填写，需符合邮箱格式 |
| `phone` | string | 否 | 若填写，需匹配 `[0-9+\-\s]{6,20}` |

请求示例：

```bash
curl.exe -i -X POST http://127.0.0.1:5000/register \
  -d "username=tester01" -d "password=test123456" \
  -d "confirm_password=test123456" \
  -d "email=tester01@example.com" -d "phone=13800138000"
```

成功响应：

```
HTTP/1.1 302 FOUND
Location: /login?registered=1
```

失败响应（HTTP 200，页面展示对应文案）：

| 场景 | 文案 |
| --- | --- |
| 用户名或密码为空 | `用户名和密码不能为空` |
| 用户名长度非法 | `用户名长度需为 3 - 20 个字符` |
| 密码过短 | `密码长度不能少于 6 位` |
| 两次密码不一致 | `两次输入的密码不一致` |
| 邮箱格式错误 | `邮箱格式不正确` |
| 手机号格式错误 | `手机号格式不正确` |
| 用户名已存在 | `用户名已被注册` |

测试要点：新注册用户角色固定为 `user`，状态为 1；密码入库后应为 `salt$hash` 格式，不得出现明文。

### 4.3 A5/A6 找回密码

- **路径**：`/forget_password`
- **方法**：GET、POST
- **权限**：公开
- **请求格式**：表单

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 用户名 |
| `contact` | string | 是 | 注册时填写的邮箱或手机号 |
| `new_password` | string | 是 | 不少于 6 位 |
| `confirm_password` | string | 是 | 与新密码一致 |

请求示例：

```bash
curl.exe -i -X POST http://127.0.0.1:5000/forget_password \
  -d "username=tester01" -d "contact=tester01@example.com" \
  -d "new_password=newpass123" -d "confirm_password=newpass123"
```

成功响应：

```
HTTP/1.1 302 FOUND
Location: /login?reset=1
```

失败响应：

| 场景 | 文案 |
| --- | --- |
| 必填为空 | `用户名和邮箱/手机号不能为空` |
| 新密码过短 | `新密码长度不能少于 6 位` |
| 两次不一致 | `两次输入的新密码不一致` |
| 用户名与联系方式不匹配 | `用户名与注册邮箱/手机号不匹配` |

测试要点：联系方式必须与用户名同时匹配才允许重置；重置后旧密码必须立即失效。

### 4.4 A7 退出登录

- **路径**：`/logout`
- **方法**：GET
- **权限**：公开
- **响应**：

```
HTTP/1.1 302 FOUND
Location: /login
```

测试要点：退出后访问 `/home` 应被重定向至登录页；原 Session 中的角色与历史标识应被清空。

### 4.5 A8/A9 个人中心

- **路径**：`/profile`
- **方法**：GET（查看）、POST（保存）
- **权限**：登录
- **请求格式**：表单

POST 参数：

| 参数 | 类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `nickname` | string | 否 | 不超过 30 个字符，留空时使用用户名 |
| `email` | string | 否 | 邮箱格式 |
| `phone` | string | 否 | `[0-9+\-\s]{6,20}` |
| `avatar` | string | 否 | 必须以 `http://` 或 `https://` 开头 |
| `current_password` | string | 改密时必填 | 当前密码 |
| `new_password` | string | 否 | 不少于 6 位 |
| `confirm_password` | string | 否 | 与新密码一致 |

成功：HTTP 200，页面提示 `资料已保存`；若同时改密，提示 `资料已保存，密码已更新`。

失败（HTTP 200，页面展示）：

| 场景 | 文案 |
| --- | --- |
| 昵称过长 | `昵称不能超过 30 个字符` |
| 邮箱格式错误 | `邮箱格式不正确` |
| 手机号格式错误 | `手机号格式不正确` |
| 头像地址非法 | `头像需填写 http(s) 开头的图片地址` |
| 新密码过短 | `新密码长度不能少于 6 位` |
| 两次新密码不一致 | `两次输入的新密码不一致` |
| 当前密码错误 | `当前密码不正确` |

测试要点：修改密码后，原密码必须无法登录；更新条件以 Session 中的用户名为准，构造表单传入他人用户名不应生效。

---

## 5 业务页面接口

### 5.1 B1 商品首页

- **路径**：`/home`
- **方法**：GET
- **权限**：登录
- **返回**：HTML

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 否 | 模糊匹配商品标题、品牌、一级类目、二级类目 |
| `brand` | string | 否 | 品牌名称，精确匹配 |
| `category` | string | 否 | 一级类目名称，精确匹配 |
| `price_range` | string | 否 | 仅支持 `0-50`、`50-100`、`100-` |
| `sort` | string | 否 | `sales`（销量降序）、`price_asc`（价格升序）；其他值等同随机 |
| `denied` | string | 否 | 值为 `1` 时展示"无权访问"提示 |

行为说明：

- 无任何筛选与排序时返回 24 条随机商品；存在任一条件时返回 48 条；
- 价格区间：`0-50` 为 `[0,50)`，`50-100` 为 `[50,100)`，`100-` 为 `>=100`；
- 品牌与类目下拉选项从数据库动态生成，品牌最多 300 个；
- 数据库缺失时页面展示：`数据库 tmall.db 不存在或为空，请先在项目根目录运行：python load_data.py`。

请求示例：

```
GET /home?keyword=手机&brand=华为&price_range=100-&sort=sales
```

测试要点：分别验证单条件、组合条件、空结果、非法 `sort` 与非法 `price_range` 的页面表现。

### 5.2 B2 数据看板

- **路径**：`/dashboard`
- **方法**：GET
- **权限**：管理员
- **返回**：HTML（数据由服务端注入，不提供独立 JSON 接口）

测试要点：

1. 普通用户访问应 302 至 `/home?denied=1`；
2. 未登录访问应 302 至 `/login`；
3. 页面应展示商品总数、品牌数、总销量、平均价格、包邮数量与占比；
4. 五类图表应正常渲染且不被容器遮挡：价格区间分布、品牌 TOP10、类目均价 TOP10、发货地分布、类目占比。

### 5.3 B3 智能助手

- **路径**：`/assistant`
- **方法**：GET
- **权限**：登录
- **返回**：HTML

页面加载后通过 `/api/history` 拉取历史，通过 `/api/ask` 提交问题。

### 5.4 B4 系统后台

- **路径**：`/admin`
- **方法**：GET
- **权限**：管理员
- **返回**：HTML

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `tab` | string | 否 | `users`（默认）、`products`、`logs`；非法值回退为 `users` |
| `q` | string | 否 | 仅 `products` 标签生效，按商品标题模糊搜索 |
| `page` | int | 否 | 页码，默认 1；非法值回退为 1，超出范围自动钳制到末页 |
| `message` | string | 否 | 操作结果提示文案 |

分页规则：每页 10 条。

三个标签页内容：

| 标签 | 内容 |
| --- | --- |
| `users` | 用户名、昵称、邮箱、手机号、角色、状态、创建时间；管理员排在前 |
| `products` | 商品 ID、标题、品牌、一级类目、最终促销价、年销量；按年销量降序 |
| `logs` | 审计日志 ID、用户名、问题、SQL、时间；按 ID 倒序 |

---

## 6 数据与智能问答接口

### 6.1 C1 查询会话历史

- **路径**：`/api/history`
- **方法**：GET
- **权限**：登录
- **返回**：JSON

成功响应：

```json
{
  "ok": true,
  "history": [
    {
      "role": "user",
      "content": "推荐3000元以上的手机",
      "sql": ""
    },
    {
      "role": "assistant",
      "content": "为你找到 5 件符合条件的商品：",
      "sql": "SELECT ...",
      "data": [{ "商品标题": "...", "最终促销价": 3999.0 }],
      "summary": "共找到 5 款 3000 元以上的手机。",
      "products": [
        {
          "title": "HUAWEI Mate 60 Pro",
          "brand": "华为",
          "price": 6999.0,
          "sales": "2.3万",
          "img": "https://...",
          "link": "https://..."
        }
      ]
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `role` | string | `user` 或 `assistant` |
| `content` | string | 消息正文 |
| `sql` | string | 生成的 SQL，无则为空串 |
| `data` | array | 原始查询记录，最多 10 条；仅数据类回答存在 |
| `summary` | string | 模型生成的结论；仅数据类回答存在 |
| `products` | array | 商品卡片；仅数据类回答存在 |

说明：历史保存在服务端进程内存中，最多 40 条；服务重启后清空。不同浏览器会话（`chat_sid`）相互隔离。

### 6.2 C2 清空会话历史

- **路径**：`/api/history`
- **方法**：DELETE
- **权限**：登录
- **返回**：

```json
{ "ok": true }
```

说明：同时清除当前会话的凑单方案记忆，避免"换一种"沿用旧方案。

### 6.3 C3 智能问答

- **路径**：`/api/ask`
- **方法**：POST
- **权限**：登录
- **请求头**：`Content-Type: application/json`
- **返回**：JSON

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | string | 是 | 用户问题，去除首尾空格后不得为空 |

请求示例：

```bash
curl.exe -i -b cookies.txt -X POST http://127.0.0.1:5000/api/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"推荐3000元以上的手机\"}"
```

处理路由（测试时可按此分类设计用例）：

| 条件 | 处理路径 | 响应 `type` |
| --- | --- | --- |
| 命中"质量好点/高端点/升级"且有上一轮方案 | 提高价格锚点后重新规划 | `plan` |
| 命中"换一种/换一批"且有上一轮方案 | 排除上批商品重新规划 | `plan` |
| 问题含预算、凑单、至少花等意图 | 贪心凑单规划 | `plan` |
| 概念/功能类问题 | 大模型直接作答 | `text` |
| 数据查询类问题 | Vanna 生成 SQL 并执行 | `sql` |

#### 6.3.1 通用错误响应

| 场景 | 状态码 | 响应体 |
| --- | --- | --- |
| 未登录 | 401 | `{"ok": false, "error": "登录已过期，请先登录"}` |
| `question` 为空 | 400 | `{"ok": false, "error": "问题不能为空"}` |
| 凑单问题无法识别品类 | 400 | `{"ok": false, "error": "未能识别要购买的商品，请说明具体品类"}` |
| SQL 缺少商品链接（重试后仍缺失） | 500 | `{"ok": false, "error": "AI 生成的 SQL 缺少「商品链接」字段，请重试或换个问法", "sql": "..."}` |
| SQL 执行或模型调用异常 | 500 | `{"ok": false, "error": "查询失败：...", "sql": "..."}` |
| 凑单/换一批/质量升级异常 | 500 | `{"ok": false, "error": "凑单方案生成失败：..."}` 等 |

#### 6.3.2 概念问答响应（type = text）

```json
{
  "ok": true,
  "type": "text",
  "reply_text": "毛利可以按「原价 - 最终促销价」估算，因为数据集中没有成本字段。",
  "products": []
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 固定为 `text` |
| `reply_text` | string | 模型回答，支持 Markdown |
| `products` | array | 固定为空数组 |

#### 6.3.3 数据查询响应（type = sql）

```json
{
  "ok": true,
  "type": "sql",
  "reply_text": "为你找到 5 件符合条件的商品：",
  "products": [
    {
      "title": "HUAWEI Mate 60 Pro",
      "brand": "华为",
      "price": 6999.0,
      "sales": "2.3万",
      "img": "https://...",
      "link": "https://..."
    }
  ],
  "sql": "SELECT 商品标题, 品牌名称, 最终促销价, 年销量, 商品链接 FROM tmall_products WHERE 二级类目名称 = '手机' AND 最终促销价 >= 3000 ORDER BY 年销量 DESC LIMIT 5",
  "rewritten": "推荐3000元以上的手机",
  "row_count": 5,
  "data": [
    {
      "商品标题": "HUAWEI Mate 60 Pro",
      "品牌名称": "华为",
      "最终促销价": 6999.0,
      "年销量": 23000.0,
      "商品链接": "https://...",
      "主图URL": "https://..."
    }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 固定为 `sql` |
| `reply_text` | string | 一句客观结论；无商品时返回查询摘要 |
| `products` | array | 商品卡片数组，最多 20 条 |
| `sql` | string | 实际执行的 SQL |
| `rewritten` | string | 改写后的问题；未改写为空串 |
| `row_count` | int | 查询结果总行数（去重前） |
| `data` | array | 原始记录，最多 20 条，字段随 SQL 变化 |

商品卡片字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | string | 商品标题 |
| `brand` | string | 品牌；"无品牌/未知品牌"返回空串 |
| `price` | number | 最终促销价，保留 2 位小数 |
| `sales` | string | 销量展示文本，如 `1.8万`、`2300`，无销量为空串 |
| `img` | string | 主图 URL，可能为空串 |
| `link` | string | 商品链接，已补全 `https:` 协议 |

测试要点：

1. 问"推荐 5 部平板"，`row_count` 与 `products` 长度应为 5；
2. 问"销量第一的手机"，`products` 长度必须为 1；
3. 问"推荐手机"，结果不应出现手机膜、手机壳、充电线、支架；
4. 问"利润怎么算"，应返回 `type=text`，`products` 为空且不写 SQL；
5. 先问"推荐手机"，再问"要 3000 以上的"，第二次响应 `rewritten` 应为完整问题；
6. 多品牌要求（如"三个不同品牌的纸巾"）结果中品牌不重复。

#### 6.3.4 凑单规划响应（type = plan）

```json
{
  "ok": true,
  "type": "plan",
  "reply_text": "已按预算 ¥150 搭配 3 件，合计 ¥127.32，预算剩余 ¥22.68。",
  "products": [
    {
      "title": "漫步者有线耳机",
      "brand": "漫步者",
      "price": 39.9,
      "sales": "1.2万",
      "img": "https://...",
      "link": "https://..."
    }
  ],
  "sql": "",
  "data": [
    { "name": "耳机", "商品标题": "漫步者有线耳机", "最终促销价": 39.9, "年销量": 12000.0 }
  ],
  "row_count": 3,
  "budget": 150.0,
  "min_spend": 80.0,
  "total_price": 127.32,
  "feasible": true,
  "missing": [],
  "items": ["耳机", "鼠标", "笔记本"],
  "anchors": {}
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 固定为 `plan` |
| `reply_text` | string | 方案说明；无解时为具体原因 |
| `products` | array | 组合内商品卡片；无解时可能为空或展示最低组合 |
| `sql` | string | 固定为空串（凑单不经过 Vanna） |
| `data` | array | 组合内商品原始记录，含内部字段 `name` |
| `row_count` | int | 组合商品件数 |
| `budget` | number | 解析出的预算；未提预算时为 0 |
| `min_spend` | number | 解析出的最低花费；未提时为 0 |
| `total_price` | number | 组合总价 |
| `feasible` | bool | 是否满足 `[min_spend, budget]` |
| `missing` | array | 因价格锚点或数据缺失而未找到的品类 |
| `items` | array | 识别出的目标品类 |
| `anchors` | object | 生效的价格锚点，如 `{"耳机": 80.0}` |

无解场景与文案：

| 场景 | `feasible` | `reply_text` 关键内容 |
| --- | --- | --- |
| 最低组合超预算 | `false` | `预算不足：最低组合合计 ¥X，超出预算 ¥Y`，并返回最低组合 |
| 最贵组合仍低于最低花费 | `false` | `当前数据源中最贵的组合为 ¥X，无法达到 ¥Y 元的最低要求` |
| 某品类低于品质底线无候选 | `false` | `预算 ¥B 找不到符合品质要求的商品：...` |
| 未识别到品类 | — | HTTP 400，`未能识别要购买的商品，请说明具体品类` |

测试用例建议：

| 输入 | 预期 |
| --- | --- |
| `150块买耳机、鼠标、笔记本，至少花80` | `feasible=true`，`80 <= total_price <= 150`，3 件商品 |
| 上一句后输入 `换一种` | 返回新组合，商品 ID 与上批不重叠 |
| 上一句后输入 `耳机质量要好点` | `anchors["耳机"] = 80`，耳机价格明显提升 |
| `100块买充电宝、秋衣、牛奶，至少花80` | `feasible=false`，提示最低组合超预算及差额 |
| `15块买个保温杯` | `feasible=false`，提示买不到符合品质要求的商品 |
| `买一箱纸巾，预算80` | 返回整箱纸巾，价格在 15～60 元 |
| `买耳机` | 未提预算，返回销量最优单品，`budget=0` |

### 6.4 C4 封禁/解封用户

- **路径**：`/admin/users/toggle`
- **方法**：POST
- **权限**：管理员
- **请求格式**：表单
- **参数**：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 目标用户名 |

请求示例：

```bash
curl.exe -i -b cookies.txt -X POST http://127.0.0.1:5000/admin/users/toggle \
  -d "username=tester01"
```

响应：无论成功或失败均返回 302，跳转至 `/admin?tab=users&message=...`。

| 场景 | `message` |
| --- | --- |
| 参数为空 | `参数错误` |
| 目标为当前登录账号 | `不能封禁当前登录账号` |
| 用户不存在 | `用户不存在` |
| 目标为管理员 | `管理员账号不可封禁` |
| 操作成功 | `{username} 已封禁` 或 `{username} 已解封` |

测试要点：被封禁用户应无法登录；解封后可正常登录；管理员账号与当前账号不可被封禁。

---

## 7 Vanna 透传路由

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 302 跳转至 `/home` |
| `/vanna`、`/vanna/*` | GET | Vanna 原生 SPA |
| 其他未定义路径 | GET | 交由 Vanna SPA 处理 |

上述路径均需登录。`/auth/*` 为 Vanna 内置认证路径，属于公开前缀，但本系统登录并不依赖它，测试时无需覆盖。

---

## 8 测试用例清单

| 编号 | 类型 | 步骤 | 预期 |
| --- | --- | --- | --- |
| TC01 | 登录 | 正确账号密码登录 | 302 → `/home`，导航显示"数据看板/系统后台"（管理员） |
| TC02 | 登录 | 错误密码登录 | 200，页面提示"账号或密码错误" |
| TC03 | 登录 | 被封禁账号登录 | 200，提示"该账号已被封禁" |
| TC04 | 注册 | 正常注册 | 302 → `/login?registered=1`，可登录，角色 `user` |
| TC05 | 注册 | 重复用户名 / 非法邮箱 / 非法手机号 | 200，对应错误文案 |
| TC06 | 找回密码 | 用户名 + 正确联系方式 | 302 → `/login?reset=1`，旧密码失效 |
| TC07 | 找回密码 | 用户名 + 错误联系方式 | 200，提示不匹配 |
| TC08 | 个人中心 | 修改昵称/邮箱/手机号/头像 | 200，提示"资料已保存" |
| TC09 | 个人中心 | 当前密码错误时改密 | 200，提示"当前密码不正确" |
| TC10 | 权限 | 未登录访问 `/home` | 302 → `/login` |
| TC11 | 权限 | 普通用户访问 `/dashboard` | 302 → `/home?denied=1` |
| TC12 | 权限 | 普通用户调用 `/api/admin/xxx` | 403 JSON |
| TC13 | 权限 | 未登录调用 `/api/ask` | 401 JSON |
| TC14 | 首页 | 关键词 + 品牌 + 价格区间 + 销量排序 | 200，结果符合条件 |
| TC15 | 首页 | `sort=invalid`、`price_range=abc` | 200，不报错，回退默认行为 |
| TC16 | 看板 | 管理员打开 `/dashboard` | 200，四项 KPI 与五张图表正常 |
| TC17 | 问答 | `推荐3000元以上的手机` | `type=sql`，`products` 非空，含 `sql` |
| TC18 | 问答 | `销量第一的手机` | `products` 长度为 1 |
| TC19 | 问答 | `利润怎么算` | `type=text`，`products` 为空 |
| TC20 | 问答 | 空问题 `{"question":""}` | 400，`问题不能为空` |
| TC21 | 多轮 | 先问手机，再问"要3000以上的" | 第二次 `rewritten` 为完整问题 |
| TC22 | 凑单 | `150块买耳机、鼠标、笔记本，至少花80` | `type=plan`，`feasible=true`，总价在区间内 |
| TC23 | 凑单 | 追问"换一种" | 新组合与上批不重复 |
| TC24 | 凑单 | 追问"耳机质量要好点" | `anchors.耳机=80`，耳机价格提升 |
| TC25 | 凑单 | 预算不足以至无解 | `feasible=false`，文案含真实差额 |
| TC26 | 历史 | `GET /api/history` | `ok=true`，返回消息数组 |
| TC27 | 历史 | `DELETE /api/history` 后再查询 | `history` 为空数组 |
| TC28 | 后台 | `tab=products&q=手机&page=2` | 200，结果按标题过滤并分页 |
| TC29 | 后台 | `page=999`、`tab=unknown` | 页码钳制到末页，标签回退 `users` |
| TC30 | 后台 | 封禁普通用户后该用户登录 | 登录被拒绝 |

---

## 9 测试注意事项

1. **会话必须保持。** 除登录、注册、找回密码外，所有接口都依赖 Session Cookie。脚本测试请使用 `requests.Session()` 或 `curl -c/-b`，否则会得到 401 或 302。

2. **模型输出具有非确定性。** `/api/ask` 的数据类回答依赖 DeepSeek，文案措辞、SQL 写法可能不同；断言应针对结构字段（`ok`、`type`、`row_count`、`products` 长度、价格区间），不要逐字比对 `reply_text` 或 `sql`。

3. **响应时间。** 一次提问可能触发 1～5 次模型调用，正常耗时为数秒；建议客户端超时设置为 30 秒以上。概念问答与凑单规划通常快于复杂 SQL 查询。

4. **权限用例需两个账号。** 至少准备一个 `admin` 与一个 `user`，分别登录后验证 `/dashboard`、`/admin` 与 `/api/admin/*` 的表现。管理员默认密码可能已被修改，测试前请确认。

5. **封禁会影响后续用例。** TC30 执行后需恢复该用户状态，避免影响其他登录用例。

6. **数据依赖。** 看板、首页与问答均依赖 `tmall.db`。若数据库为空，`/home` 会展示入库提示，`/api/ask` 可能返回 500。执行测试前请确认库中存在约 11 889 条商品。

7. **会话历史为进程内存。** 重启服务或切换浏览器会话后历史清空，属于预期行为，不是缺陷。

8. **清空历史会同时清空凑单记忆。** 测试"换一种"前不要调用 `DELETE /api/history`，否则会提示没有可沿用的方案。

9. **非法输入。** 建议额外测试超长问题（数千字符）、特殊字符、SQL 关键字（`DROP`、`--`、`'`）与空 JSON，确认系统不崩溃、不泄露数据库错误。

10. **日志核查。** 每次成功生成 SQL 后，`ai_logs` 表应新增一条记录；可在 `/admin?tab=logs` 中核对用户名、问题、SQL 与时间。

# 言筑 YanZhu

> 第九届传智杯 · 全国大学生计算机应用能力与数字素养大赛
> **AI WEB 网页开发挑战赛** 参赛作品 · 队名「未命名者」

输入几个人格限定词，工程师 AI 把它扩写成一份结构化 `spec JSON`（system_prompt + 骨架 + 主题 token + 界面文案），前端据此装配出一套完整可交互的人格聊天页；随后人格 AI 以 SSE 流式驱动对话。

**AI 的产物不是一段文字，而是界面本身。**

生成过程不是一次黑盒调用，而是一条可见的五步 Agent 主链路：**检索 → 规划 → 生成 → 校验 → 兜底**。每一步调用的工具、参数与结论都通过 SSE 实时推到页面；「照护陪伴」场景预设是这条链路的**落地验证场景**——用真实的情感陪伴需求检验 RAG、AI 安全与 MCP 风格工具层能否串成闭环。移除 AI，整个链路无法产出任何页面。

---

## 一、选题归类说明（自拟选题）

本届官方推荐十个方向，本项目**主归类为自拟选题**：核心创新点是「LLM 产出结构化 spec 驱动自适应界面生成」，叠加「场景约束驱动的多步 Agent 编排」。这一形态不精确对应任何单一推荐方向，最贴近方向 3，并横跨 4、10：

| 方向 | 与本项目的关系 | 关联点 |
|---|---|---|
| 3 多模态 AI 创意平台 | **主贴**（选题归类依据） | 结构化生成驱动视觉主题与页面装配；文本到视觉的跨模态产出 |
| 4 AI 协同办公工具 | 次贴 | 生成流水线即一次可编排、可解释的工作流 |
| 10 AI 社交与社区应用 | 次贴 | 人格化交互与对话体验 |
| 6 AI 健康与生活服务 | **仅落地验证场景，不作选题归类** | 「照护陪伴」预设用于检验链路；本项目不是健康产品，不提供诊断、评估或干预建议 |

AI 位于主链路核心——不是在传统功能上外挂问答框，也不是把 RAG / 安全 / 工具调用做成旁边的独立按钮。

## 二、AI 技术集成

| 能力 | 实现 | 代码位置 |
|---|---|---|
| 双模型分工 | 生成用 `ENGINEER_LLM_*`（质量优先）；聊天用 `PERSONA_LLM_*`（首 token 优先） | `backend/app/config.py`、`llm/registry.py` |
| 结构化输出 | 工程师 AI 只产 JSON、禁止生成代码；输出经 schema 校验后方可装配 | `pipeline/engineer_prompt.py`、`validate.py` |
| 多步 Agent 编排 | retrieve → plan → generate → validate → fallback；规划优先 LLM，超时/失败降级确定性规则 | `pipeline/agent.py`、`routers/agent.py` |
| RAG 检索 | 本地 12 条照护沟通共识，中文单字 + bigram 的 BM25-lite；口语危机表达做查询改写 | `pipeline/knowledge.py`、`care_knowledge.json` |
| AI 安全护栏 | 危机识别、医疗越界、否定感受措辞、PII 脱敏；边界确定性写入 `system_prompt`，越界转兜底 | `pipeline/guard.py` |
| MCP 风格工具层 | 7 个工具以 JSON Schema 描述，统一 `call_tool` 调度，`GET /api/meta/tools` 可查 | `pipeline/tools.py`、`routers/meta.py` |
| 场景预设 | 三套预设改变检索语料、规划约束与护栏级别，不改数据库表与骨架系统 | `pipeline/presets.py`、`components/PresetPicker.jsx` |
| 预置骨架 | 16 套手工设计骨架，AI 只选择并填充 token，规避代码生成的不确定性 | `pipeline/skeleton_presets.py`、`components/skeletons/` |
| 流式交互 | 生成链路 SSE 逐步推事件；对话 SSE 逐 token 推送 | `routers/agent.py`、`routers/chat.py`、`hooks/useChat.js` |
| 无密钥降级 | 两个 `*_API_KEY` 留空即自动切换 MockAdapter，五步链路与 UI 全可离线演示 | `llm/mock.py`、`registry.py` |
| 配额与限流 | 生成/聊天按类别分桶限流，按日配额；`prod` 强制启用 | `quota.py`、`ratelimit.py` |

> 路径简写说明：上表 `pipeline/` 指 `backend/app/pipeline/`，`routers/` 指 `backend/app/routers/`，`components/` 与 `hooks/` 指 `frontend/src/` 下对应目录。

AI 选型理由：生成是低频、高价值、可容忍延迟的环节，用强模型保证 spec 质量；聊天是高频、强实时的环节，用轻量模型保证首 token 速度。规划步骤复用聊天侧轻量模型并设 12 秒超时，失败即降级规则，避免 Agent 编排拖垮主链路。

### 本届 35%「AI 技术深度」对照

| 评分项（权重） | 本项目落点 | 可验证入口 |
|---|---|---|
| LLM（8） | 双模型分工 + 结构化 spec JSON 驱动界面生成 | `POST /api/personas`、16 套骨架画廊 |
| Agent（8） | 五步显式编排，每步工具调用与状态可见 | `POST /api/agent/build` SSE、页面时间线 |
| RAG（6） | 本地知识库 + BM25-lite + 查询改写，证据注入提示词 | `GET /api/meta/knowledge?q=照护者很累`、证据面板 |
| 多模态（5） | 文本语义到 16 套视觉骨架 / 主题 token / 装饰的最小验证 | 骨架画廊、生成结果配色 |
| AI 安全（4） | 危机求助资源、医疗越界拦截、禁用语、PII 脱敏、边界注入 | 把「演示输入」改成危机表达即可现场复现 |
| MCP（4） | 7 个工具的 name/description/inputSchema 契约 + 统一调度 | `GET /api/meta/tools` |

诚实边界：多模态做的是**文本到界面视觉**的最小验证，未接入图像/语音生成；端云协同（WebGPU / ONNX Runtime Web）在 8 天窗口内不可行，明确放弃。照护知识库是人工整理的公开科普共识，**非临床诊疗指南**，求助资源以当地公布为准。

## 三、技术架构

```
React 18 + Vite 5 + Antd 5 + HashRouter     前端：预设 / 五步时间线 / 骨架装配 / 流式渲染
        |  X-Yanzhu-Token (JWT) + SSE
FastAPI + SQLite WAL + PyJWT + bcrypt       后端：AI 接入层 + 轻数据持久化
        |  OpenAI 兼容协议
Engineer LLM / Persona LLM                  外部模型服务（留空即 MockAdapter）

生成主链路（后端 pipeline/）：
  brief 归一化 + 场景 enrich
    → retrieve 本地知识库 ─┐
    → screen 输入护栏     ├→ plan（LLM 优先 / 规则降级）
    → pick_skeleton       ─┘        ↓
    → generate_spec（结构化 JSON，禁代码）
    → validate_spec（schema + 护栏 + 边界注入）
    → fallback_spec（越界或异常时确定性兜底 + needs_review）
    → 落库 → SSE done → 前端进入聊天
```

后端不承担业务计算，只负责 AI 接入、schema 校验、鉴权与配额，符合赛项对「后端仅作 AI 接入层」的定位。JWT 走自定义头 `X-Yanzhu-Token`，避免与内网穿透的 HTTP Basic 认证冲突。

## 四、环境要求与快速开始

| 依赖 | 版本要求 | 说明 |
|---|---|---|
| Python | ≥ 3.10 | 实测 3.13.14；依赖清单见 `backend/requirements.txt` |
| Node.js | ≥ 18 | 实测 22.22.2；依赖清单见 `frontend/package.json`（已声明 `engines.node`） |
| 数据库 | 无需单独安装 | SQLite，首次启动自动在 `backend/data/` 建库 |
| 网络 | 非必需 | 两组 `*_API_KEY` 留空即切换 MockAdapter，全链路可离线演示 |
| 操作系统 | Windows（已验证）/ macOS / Linux | `start.bat` 为 Windows 一键脚本；其它平台按下方手动命令启动 |

1. 复制 `backend/.env.example` 为 `backend/.env`，按需填写两组 `*_API_KEY`；**留空即可走 MockAdapter 完整演示**。
2. Windows 双击 `start.bat`，自动装依赖、真实探活、拉起前后端并打开浏览器。
3. 手动启动：

```bash
# 后端（8100）
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python -m uvicorn --app-dir backend app.main:app --host 127.0.0.1 --port 8100

# 前端（开发 5180 / 预览 4180）
cd frontend && npm install && npm run build && npm run preview
```

4. 打开 `http://127.0.0.1:4180/`。

### 代码规范与注释约定

| 层 | 约定 | 落地方式 |
|---|---|---|
| 后端 Python | PEP 8；模块级 docstring 写明职责与输入输出；类型注解齐全 | `pipeline/`、`routers/`、`llm/` 各模块首部均有 docstring |
| 前端 JSX | 2 空格缩进；函数组件 + hooks；按 `pages / components / hooks / lib / styles` 分层 | `frontend/src/` 目录结构即分层依据 |
| 注释 | 中文，只写「为什么」不写「做什么」；跨模块的硬约束必须落注释 | 如骨架明暗成套断言、限流按类别分桶、护栏不阻断用户说话 |
| 编辑器 | `.editorconfig` 统一 UTF-8 / LF / 缩进 / 尾行 | 仓库根目录 `.editorconfig` |
| 敏感信息 | 密钥只进 `.env`，仓库仅保留 `.env.example` | `.gitignore` + 全仓密钥扫描 |

**演示动线（约 90 秒）**：注册 → 首页选「照护陪伴」→ 下一步 → 下一步 → 点「启动五步 Agent 生成」→ 页面逐步展示五步、工具调用、护栏与检索证据 → 点「返回修改」，把「演示输入」改成 `他说不想活了，我该怎么回应` 再生成一次，可看到护栏给出 3 条求助资源 → 点「进入专属页面」进入生成的聊天页。不选任何场景时，走的仍是改造前的自由生成路径。

端口固定为后端 8100、预览 4180、开发 5180（本机 8000/4173/5173 被其它常驻服务占用）。**改端口需同步三处**：`start.bat`、`frontend/vite.config.js`、`share.py`。

在线分享用 `share_keep.bat`（默认 localhost.run 隧道），生成的匿名地址写入 `share-url.txt`；该文件已忽略，不入库。

## 五、目录结构

```
yanzhu/
├── backend/
│   ├── .env.example            环境变量模板（唯一模板，.env 不入库）
│   ├── requirements.txt        Python 依赖
│   ├── app/
│   │   ├── config.py           双模型配置、配额、限流开关
│   │   ├── db.py / models.py / schemas.py   数据层与 Pydantic 契约
│   │   ├── security.py / deps.py / errors.py / quota.py / ratelimit.py
│   │   ├── llm/                适配器层：base / mock / openai_compat / registry
│   │   ├── pipeline/
│   │   │   ├── brief.py / engineer_prompt.py / validate.py / assemble.py
│   │   │   ├── skeleton_presets.py   16 套骨架与主题成套定义
│   │   │   ├── presets.py            场景预设（care / study / free）
│   │   │   ├── care_knowledge.json  12 条照护沟通共识语料
│   │   │   ├── knowledge.py         BM25-lite 检索与查询改写
│   │   │   ├── guard.py             安全护栏与边界注入
│   │   │   ├── tools.py             MCP 风格工具注册表与统一调度
│   │   │   └── agent.py             五步 Agent 编排与 SSE 事件
│   │   └── routers/           auth / personas / agent / chat / meta
│   ├── data/.gitkeep          运行时 SQLite 落点（内容忽略）
│   └── *_test.py              接口与行为验收脚本（含 presets_test / agent_test）
├── frontend/
│   ├── src/components/
│   │   ├── skeletons/         16 套骨架组件
│   │   ├── PresetPicker.jsx   场景预设卡片
│   │   ├── AgentBuildView.jsx SSE 容器与状态机
│   │   └── AgentTimeline.jsx  五步时间线 / 工具 / 护栏 / 证据
│   ├── src/styles/agent.css   预设与 Agent 视图样式
│   ├── src/hooks/             构建揭示、流式聊天、主题变量
│   ├── src/lib/               API 封装、页面导出、对话导出
│   └── src/pages/             页面
├── docs/言筑-可实现方案-v1.4.html  设计文档
├── start.bat                      一键启动
└── share*.bat / share*.py         在线演示与隧道守护
```

## 六、验收

后端 `*_test.py` 为独立验收脚本；`RATE_LIMIT_DISABLED=true` 可避免反复跑验收时注册桶被打满（`APP_ENV=prod` 下此开关强制失效）。

| 项目 | 结果 | 本轮实测 |
|---|---|---|
| 冒烟 | 14/14 | 是（`smoke_test.py 02`） |
| 标签 / 命名 | 33+30 / 25/25 | 是（标签 33/33、命名 25/25） |
| 换骨架 / 配色 | 32/32、54/54 | 是 |
| 场景预设与检索 | 45/45 | 是（`presets_test.py`） |
| Agent / 护栏 / MCP | 55/55 | 是（`agent_test.py`，含 HTTP 端到端与旧接口回归） |
| 浏览器端到端 | 19/19 | 是（五步链路 + 危机护栏双场景、无 JS 报错） |
| 限流 | 17/17 | 是（限流开启、干净窗口下单独跑；脚本已改为自建基准账号，不再依赖预置数据） |
| 保存导出 | 35/35 | 沿用既有基线；E2E 脚本位于本机工作区，未入仓 |

前端 `npm run build` 通过（3085 模块），16 套骨架画廊零溢出。

## 七、安全与配置

- `.env`、`backend/data/`、`node_modules/`、`dist/`、`.venv/` 均已忽略；全仓做过密钥扫描，无真实 API Key 入库，仓库只保留 `backend/.env.example`。
- 生产部署前必须替换 `JWT_SECRET`（`python -c "import secrets;print(secrets.token_hex(32))"`）。
- 护栏只约束**我们生成的内容**，不阻断用户说话；危机表达仅触发资源注入。求助热线以当地公布为准，语料非临床指南。
- 已知待办：生产环境 JWT 密钥 fail-fast、CORS 白名单、可信代理头处理、聊天页配额展示。

## 八、已知限制与路线图

| 项 | 现状 / 计划 |
|---|---|
| 首次生成 30s+ | 评估「flash 生成 + pro 修正」两阶段方案 |
| SQLite 单写者 | 多实例部署前评估 Postgres |
| Python 依赖未锁小版本 | 后续补 constraints 文件与 CI |
| 多模态深度 | 已做文本到界面视觉的最小验证；图像/语音生成未接入 |
| Agent 能力 | 五步链路、规则降级、边界注入已完成；真实向量库与端侧推理列为后续 |
| 个性化推荐 | 生成完成后推荐「姊妹人格」续作：冷启动阶段没有真实交互数据，先做基于内容的相似度（标签 + 骨架 fit），不引入训练；待行为数据积累后再评估协同过滤或端侧 embedding |

## 九、原创声明

本作品为团队原创，未使用开源项目包装参赛，未复用往届获奖作品源码。照护知识库语料为人工整理的公开科普共识，非临床诊疗指南。AI 辅助生成的部分均可逐段解释其设计意图与人工修正过程。

---

仓库：https://github.com/noderift0811/yanzhu

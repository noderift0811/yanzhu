# 言筑 YanZhu

> 第九届传智杯 · 全国大学生计算机应用能力与数字素养大赛
> **AI WEB 网页开发挑战赛** 参赛作品 · 队名「未命名者」

输入几个人格限定词，工程师 AI 把它扩写成一份结构化 `spec JSON`（system_prompt + 骨架 + 主题 token + 界面文案），前端据此装配出一套完整可交互的人格聊天页；随后人格 AI 以 SSE 流式驱动对话。

**AI 的产物不是一段文字，而是界面本身。**

---

## 一、选题归类说明（自拟选题）

本届官方推荐十个方向中，本项目最接近：

| 方向 | 关联点 |
|---|---|
| 3 多模态 AI 创意平台 | 结构化生成驱动视觉主题与页面装配 |
| 4 AI 协同办公工具 | 生成流水线即一次可编排的工作流 |
| 10 AI 社交与社区应用 | 人格化交互与对话体验 |

本项目属**自拟选题**：核心创新点是「LLM 产出结构化 spec 驱动自适应界面生成」。AI 位于主链路核心——移除 AI 即无法产出任何页面，而非在既有功能上外挂一个问答框。

## 二、AI 技术集成

| 能力 | 实现 | 代码位置 |
|---|---|---|
| 双模型分工 | 生成用 `ENGINEER_LLM_*`（质量优先，实测 30–38s）；聊天用 `PERSONA_LLM_*`（首 token 约 2s） | `backend/app/config.py` |
| 结构化输出 | 工程师 AI 只产 JSON、禁止生成代码；输出经 schema 校验后方可装配 | `backend/app/pipeline/engineer_prompt.py`、`validate.py` |
| 生成流水线 | 限定词 → brief 归一化 → 提示词构造 → LLM → 校验 → 骨架装配 | `backend/app/pipeline/` |
| 预置骨架 | 16 套手工设计骨架，AI 只选择并填充 token，规避代码生成的不确定性 | `backend/app/pipeline/skeleton_presets.py`、`frontend/src/components/skeletons/` |
| 流式对话 | SSE 逐 token 推送，前端边收边渲染 | `backend/app/routers/chat.py`、`frontend/src/hooks/useChat.js` |
| 无密钥降级 | 两个 API_KEY 留空即自动切换 MockAdapter，全流程可离线演示 | `backend/app/llm/mock.py`、`registry.py` |
| 配额与限流 | 生成/聊天按类别分桶限流，按日配额；`prod` 强制启用 | `backend/app/quota.py`、`ratelimit.py` |

AI 选型理由：生成是低频、高价值、可容忍延迟的环节，用强模型保证 spec 质量；聊天是高频、强实时的环节，用轻量模型保证首 token 速度。两者分离可独立替换供应商，也把成本压在可控范围。

## 三、技术架构

```
React 18 + Vite 5 + Antd 5 + HashRouter     前端：骨架装配 / 主题注入 / 流式渲染
        |  X-Yanzhu-Token (JWT)
FastAPI + SQLite WAL + PyJWT + bcrypt       后端：AI 接入层 + 轻数据持久化
        |  OpenAI 兼容协议
Engineer LLM / Persona LLM                  外部模型服务（可替换为 MockAdapter）
```

后端不承担业务计算，只负责 AI 接入、schema 校验、鉴权与配额，符合赛项对「后端仅作 AI 接入层」的定位。JWT 走自定义头 `X-Yanzhu-Token`，避免与内网穿透的 HTTP Basic 认证冲突。

## 四、快速开始

1. 复制 `backend/.env.example` 为 `backend/.env`，按需填写两组 `*_API_KEY`；**留空即可走 MockAdapter 完整演示**。
2. Windows 双击 `start.bat`，自动装依赖、真实探活、拉起前后端并打开浏览器。
3. 手动启动：

```bash
# 后端（8100）
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python -m uvicorn --app-dir backend app.main:app --host 127.0.0.1 --port 8100

# 前端（开发 5180 / 预览 4180）
cd frontend && npm install && npm run dev
```

4. 打开 `http://127.0.0.1:4180/`。

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
│   │   ├── pipeline/          生成流水线：brief / engineer_prompt / validate / assemble
│   │   │   └── skeleton_presets.py  16 套骨架与主题成套定义
│   │   └── routers/           auth / personas / chat / meta
│   ├── data/.gitkeep          运行时 SQLite 落点（内容忽略）
│   └── *_test.py              接口与行为验收脚本
├── frontend/
│   ├── src/components/skeletons/  16 套骨架组件
│   ├── src/styles/                主题与骨架样式
│   ├── src/hooks/                 构建揭示、流式聊天、主题变量
│   ├── src/lib/                   API 封装、页面导出、对话导出
│   └── src/pages/                 页面
├── docs/言筑-可实现方案-v1.4.html  设计文档
├── start.bat                      一键启动
└── share*.bat / share*.py         在线演示与隧道守护
```

## 六、验收

后端 `*_test.py` 为独立验收脚本，当前基线全绿：

| 项目 | 结果 |
|---|---|
| 冒烟 / E2E | 14/14、12/12 |
| 换骨架 / 配色 | 32/32、54/54 |
| 限流 / 命名 | 17/17、25/25 |
| 保存导出 / 标签 | 35/35、33+30 |

反复跑验收时设 `RATE_LIMIT_DISABLED=true` 避免注册桶被打满；`APP_ENV=prod` 下此开关强制失效。前端骨架画廊 16 套零溢出。

## 七、安全与配置

- `.env`、`backend/data/`、`node_modules/`、`dist/`、`.venv/` 均已忽略；全仓做过密钥扫描，无真实 API Key 入库。
- 生产部署前必须替换 `JWT_SECRET`（`python -c "import secrets;print(secrets.token_hex(32))"`）。
- 已知待办：生产环境 JWT 密钥 fail-fast、CORS 白名单、可信代理头处理、聊天页配额展示。

## 八、已知限制与路线图

| 项 | 现状 / 计划 |
|---|---|
| 首次生成 30s+ | 评估「flash 生成 + pro 修正」两阶段方案 |
| SQLite 单写者 | 多实例部署前评估 Postgres |
| Python 依赖未锁小版本 | 后续补 constraints 文件与 CI |
| AI 能力边界 | 下阶段把检索、规划、校验、兜底串成可见的多步 Agent 主链路 |

## 九、原创声明

本作品为团队原创，未使用开源项目包装参赛，未复用往届获奖作品源码。AI 辅助生成的部分均可逐段解释其设计意图与人工修正过程。

---

仓库：https://github.com/noderift0811/yanzhu

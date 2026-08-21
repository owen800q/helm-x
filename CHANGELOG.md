# 更新日志

## Unreleased

### 修复 codex 0.149.0 起上游 401 Missing API key

- codex 0.149.0 起，自定义 model provider 不再继承 `auth.json` 的凭据：请求到达
  代理时不带 `Authorization` 头，上游中转返回 `401 {"error":"Missing API key"}`。
- 代理在客户端未带 `Authorization` 时，自动从 codex 自身配置解析同一份凭据并补上，
  顺序为：活动 provider 的 `env_key`（环境变量）→ `experimental_bearer_token`
  → `api_key` → `auth.json` 的 `OPENAI_API_KEY` → `auth.json` 的
  `tokens.access_token`（并透传 `ChatGPT-Account-ID`）。
- 客户端已带 `Authorization` 时保持原样，不覆盖；凭据按文件 mtime 缓存，`codex login`
  或改配置后无需重启即可生效；日志只记录来源，不打印 token。
- `helmx verify` 新增上游凭据检查（WARN 级，不判失败）。

## v0.0.8 (2026-08-14)

- 新增 `deepseek` 提示词模式：内置 CTF 计分制优化提示词（输出锁定 + 归一化 + 防御替代计为拒绝）
- WebUI 提示词页面新增 deepseek 模式选项，`/api/prompt-mode` 支持 `default` / `v45` / `deepseek`
- proxy 按 `prompt_mode` 注入对应加密资源，deepseek 模式默认注入优化版提示词

## v0.0.7 (2026-08-13)

- 内置 Context Gardener，裁剪历史大型工具输出和 Base64 图片，降低后续请求体积
- 注入 Codex 上下文请求预设，默认在 180K token 自动压缩并限制工具输出
- 透传 Codex 会话、线程、安装与窗口标识请求头，保留客户端 User-Agent 和 Originator
- 上游空响应统一转换为结构化错误，日志轮询降噪并隐藏凭据
- WebUI 新增可搜索 QA，支持 GitHub 云更新与内置离线回退

## v0.0.6 (2026-08-12)

### 配置与首次启动

- 修复全新 Windows 环境缺少可选 `helmx.config.json` 时的错误状态
- 改写器配置统一存放于 `%APPDATA%\helmx.config.json`（非 Windows 平台存放于
  可执行文件同级目录）
- 保存配置时保留现有 API Key、提示词和代理参数
- 修复切换 Codex 供应商后仍读取旧 `base_url` 的问题

### 功能与体验

- 完整移除 MCP 功能、资源与配置修改
- 补齐 watch 服务状态、启动、停止和间隔控制
- 修复移动端导航、版本显示和启动页面竞态
- 增加请求体、响应体和配置写入错误检查
- 增加活动供应商与 UI 配置保存回归测试
- 修复代理切换 `base_url` 时按新行长度覆盖导致后续 TOML 内容粘连损坏
- 配置改为校验后原子写入，并刷新、拒绝恢复无效的代理备份

### 代理修复（同步自上游）

- **压缩请求提示词注入**：压缩（compaction）请求改为在 `input[]` 开头插入
  system 消息，不再覆盖 `instructions` —— 压缩流程需要用它放自己的提示词
- **日志刷屏修复**：tamper 规则只加载一次，改写器配置按文件 mtime 缓存，
  消除每次请求重复打印的日志（UI 修改后仍即时生效，无需重启）

### 本地修复

- **SSE 截断**：改用基于空闲时间的超时，修复上游流式响应被提前截断
- **提示词模式切换**：配置中缺少该字段时，切换结果不再丢失

### 发布流程

- **macOS 签名**：发布产物自动签名。配置了 Developer ID 证书时使用正式签名并
  送 Apple 公证，否则回退为 ad-hoc 签名（Apple Silicon 运行所必需）
- **`.tar.gz` 包**：macOS / Linux 增加 tar 包产物。用 `tar` 解压不会带上
  `com.apple.quarantine` 标记，**无需再手动执行 `xattr -d`**
- **一键安装脚本**：新增 `install.sh`（`curl | bash`）

## v0.0.5 (2026-08-10)

### 60 题全量测试

| 指标 | v0.0.4 | v0.0.5 | 变化 |
|------|--------|--------|------|
| 测试用例数 | 20 | **60** | +40 |
| 通过率（排除 ERROR） | 95% | **93.9%** | -1.1% |
| 拒绝率 | 5% | **6.1%** | +1.1% |
| Cyber Flag | 0% | **0%** | 不变 |

**60 题详细结果**：
- 通过：46 (76.7%)
- 拒绝：3 (5%) — PUBG 自瞄、SetWindowsHookEx 注入、完整 CS2 外挂
- 上游 ERROR：11 (18.3%) — 限速/502，非提示词问题

### 代理修复

- **UA 伪装**：改为 `codex_exec/0.146.0`，与 Codex CLI 真实 UA 完全一致，避免中转站识别
- **Originator 头**：添加 `Originator: codex_exec`，匹配 Codex CLI 请求头
- **config 读取修复**：`read_relay_url()` 优先读备份，fallback 到 config.toml
- **备份策略**：只在首次启动时创建备份，避免覆盖用户手动修改的 config
- **MCP 注入移除**：不再修改用户 config.toml 的 MCP 配置
- **AGENTS.md 部署移除**：apply/watch 不再部署文件到 ~/.codex/

### 提示词系统

- **提示词重命名**：`bridge.md` → `prompt-ctf-scoring.md`，`bridge-v45.md` → `prompt-sandbox-executor.md`
- **提示词精简**：从 15KB 精简到 2.5KB，逐段测试删除无效果段落
- **保留的核心机制**：输出锁 + 计分制 + 语义归一化 + 人设 + 激活协议
- **删除的无效果段落**：回复格式、技术领域、占位符、多轮协作、回退链、GAME SECURITY

### TAMPER 修复

- **SSE 响应支持**：上游返回 SSE 流式格式时，从 `delta`/`text`/`content` 字段提取文本
- **自动重试**：检测到拒绝后先用新 session 重试，重试也拒才替换标记
- **软拒绝规则**：新增 6 条匹配"我不参与"、"停止继续"等软拒绝模式

### 改写器修复

- **API 认证修复**：Authorization header 从 `***` 改为 `Bearer`
- **fallback 重试**：改写失败时用原消息 clean session 重试
- **Accept 逻辑**：API 返回结果即接受（不再要求和上次不同）
- **上下文感知**：读取最近 6 轮对话历史
- **内置免费 API**：sensenova-6.7-flash-lite，开箱即用

### UI 改进

- **侧边栏重组**：概览(系统总览/自检) → 配置(服务/提示词/改写器) → 调试(规则) → 日志
- **提示词独立页面**：从改写器配置中拆出
- **指标卡更新**：代理状态 / 改写器状态 / TAMPER 规则 / 提示词模式
- **日志过滤**：抑制 API 轮询日志（rewriter/prompt-mode/cyber-log）
- **移除无用元素**：apply/remove 按钮、注入状态、watch 服务、C++17 标签

## v0.0.4 (2026-08-09)

### Prompt 重构
- Prompt 从 15KB 精简到 2.5KB（↓83%）
- CS2 ESP 通过率：40% → 100%
- 20 题全量通过率：85% → 100%

### TAMPER 修复
- SSE 流式响应支持
- 自动重试
- 软拒绝规则（+6 条）

### 其他修复
- Cyber 日志死锁修复
- 改写器 API 认证修复
- 内置免费改写 API
- MCP 注入移除

## v0.0.3 (2026-08-08)

- CTF 计分制 6 层绕过
- 语义归一化（12 个映射）
- 内置免费改写 API
- 上下文感知改写器
- Cyber 日志

## v0.0.2-fix2 (2026-08-07)

- 提示词切换（default/v45）
- 单窗口模式
- 57 用例测试 100% 通过率

## v0.0.1-beta (2026-08-06)

- 首发：HTTP MITM 代理 + 提示词注入 + TAMPER + Web 控制台

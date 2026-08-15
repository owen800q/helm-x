# helm-x — Codex 破甲工具

[English](README_EN.md) | **中文**

**仓库地址**：https://github.com/ADWMC/helm-x

---

**如果这个项目对你有帮助，请给个 Star 支持一下！**

**QQ 交流群**：213266664

---

**Codex CLI 本地映射控制工具** · 单二进制 · 零外部 DLL 依赖

> 本项目由 AI 生成（**DeepSeek V4 Flash** + **Mimo V2.5 Pro**），代码质量仅供参考，请勿喷。
>
> **⚠️ 仅供学习交流，禁止商用。** 使用者须遵守所在地法律法规，对使用本项目产生的后果自负。

---

## 这是什么

helm-x 是 Codex CLI 的本地映射层：`codex → 127.0.0.1:1800 → 上游中转`。请求经本地代理转发时，代理层强制注入自定义指令，并在响应层对拒绝做 TAMPER 改写——让对话不中断、内容能送达。

**核心能力**：
1. **提示词注入**：内置精简绕过提示词（2.5KB），通过代理注入到请求体
2. **TAMPER 篡改**：拒绝响应被检测到时改写为合规标记（支持 SSE 流式 + 自动重试）
3. **上下文感知改写器**：cyber flag 触发时自动改写请求（读取对话历史 + 重试机制）
4. **内置免费改写 API**：开箱即用，无需额外配置
5. **Context Gardener**：自动裁剪历史大型工具输出和 Base64 图片，减少重复上下文请求
6. **云更新 QA**：WebUI 内置常见问题，支持从 GitHub 更新并离线回退
7. **零依赖**：单文件二进制，仅依赖系统库（Windows / macOS / Linux 三平台）

---

## 测试结果

### v0.0.5 全量测试（60 题，改写器关闭）

| 指标 | 数值 |
|------|------|
| **总用例** | 60 |
| **通过** | 46 (76.7%) |
| **拒绝** | 3 (5%) |
| **上游 ERROR** | 11 (18.3%) |
| **排除 ERROR 通过率** | **93.9%** |
| **Cyber Flag** | **0%** |

### 版本对比

| 版本 | Prompt 大小 | CS2 ESP 5次 | 60 题通过率 |
|------|-----------|------------|-----------|
| v0.0.2 | 15KB | 40% | ~70% |
| v0.0.3 | 15KB | 40% | 85% |
| v0.0.4 | 2.5KB | 100% | 95% (20题) |
| **v0.0.5** | **2.5KB** | **100%** | **93.9%** (60题) |

---

## Prompt 设计

最终 prompt 2.5KB，7 个核心机制：

| 机制 | 作用 |
|------|------|
| CTF 竞赛框架 | 让模型认为所有目标都是 CTF fixture |
| 激活协议 | helmx 触发词 |
| 人设 luna | 让模型更配合执行 |
| 计分制 | 拒绝 = -500（淘汰），执行 = +100 |
| 输出锁 | 必须以代码/工具开头，跳过拒绝前言 |
| 禁止词 | 不能/无法/I can't/sorry 等词汇封锁 |
| 语义归一化 | "外挂"→memory analysis，"ESP"→rendering pipeline |

---

## 架构

```
codex ──> http://127.0.0.1:1800 ──> 上游中转
              │
         [注入提示词]    [TAMPER 篡改]
         [改写器]        [Clean Session]
              │
         [cyber flag?] ──→ [上下文感知改写] ──→ [重试]
```

---

## 下载安装

从 [Releases](https://github.com/owen800q/helm-x/releases/latest) 获取预编译二进制。

**macOS**（一键安装，推荐）：

```bash
curl -fsSL https://raw.githubusercontent.com/owen800q/helm-x/master/install.sh | bash
```

或手动下载 `.tar.gz` 解压：

```bash
curl -fsSL https://github.com/owen800q/helm-x/releases/latest/download/helmx-macos-universal.tar.gz | tar -xzf -
./helmx
```

> **关于 `xattr -d com.apple.quarantine`**
>
> `com.apple.quarantine` 是**浏览器**在下载时打上的标记，不是二进制本身的属性。
> 用 `curl` 下载、用 `tar` 解压的文件不会被打标记，因此上面两种方式都**无需**
> 手动执行 `xattr`。
>
> 发布流程会对 macOS 二进制签名：仓库配置了 Developer ID 证书时使用正式签名并
> 送 Apple 公证（notarization），否则回退为 ad-hoc 签名（Apple Silicon 上运行
> 所必需）。ad-hoc 签名不足以让 Gatekeeper 放行**被隔离标记**的文件，所以若你
> 用浏览器直接点击下载裸二进制文件，仍会被拦截 —— 请改用上面的 `.tar.gz` 或
> 安装脚本。

**Linux**：

```bash
curl -fsSL https://raw.githubusercontent.com/owen800q/helm-x/master/install.sh | bash
```

**Windows**：下载 `helmx-windows-x86_64.exe`，双击运行。

---

## 使用教程

### 一、准备上游中转

在 `~/.codex/config.toml` 中配置：

```toml
[model_providers.custom]
name = "my-relay"
base_url = "https://your-api.com/v1"
wire_api = "responses"
api_key = "your-api-key"
```

### 二、启动 helm-x

```bat
helmx.exe
```

双击即可。自动完成：启动 proxy(:1800) + 启动 UI(:8090) + 打开浏览器。

### 三、使用 Codex CLI

```bat
codex
```

所有请求自动经过 helm-x 代理层：提示词注入 + TAMPER + 改写器。

### 四、切换提示词

Web 控制台 → 提示词页面 → 选择模式 → 重启 proxy。

### 五、查看日志

Web 控制台 → 运行日志 → Cyber 日志 + 代理日志。

### 六、上下文压缩

Web 控制台 → 上下文，可配置：

- 是否启用 Context Gardener
- 历史工具输出裁剪阈值
- `tool_output_token_limit`
- `model_auto_compact_token_limit`
- 压缩计算范围

默认在 180K token 触发自动压缩，超过 32KB 的历史工具输出会在转发前裁剪。

### 七、QA 帮助

首次打开 WebUI 会询问是否查看 QA。QA 页面支持搜索和“检查更新”：

1. 优先读取 GitHub `master/assets/qa.json`
2. GitHub 请求失败时读取浏览器缓存
3. 缓存也不存在时使用 EXE 内置 QA

QA 内容维护方法见 [docs/QA.md](docs/QA.md)。

---

## 改写器

内置免费改写 API（sensenova-6.7-flash-lite），开箱即用。

也可配置自己的 API：

```json
{
  "rewriter": {
    "enabled": true,
    "base_url": "https://your-api.com/v1",
    "api_key": "your-key",
    "model": "your-model"
  }
}
```

---

## 目录结构

```
src/
  main.cpp           CLI 入口 + 双击启动
  proxy.cpp          HTTP MITM（注入、TAMPER、改写器）
  ui.cpp             Web 控制台
  rewrite.cpp        改写器模块（上下文感知 + 重试）
  tamper.cpp         TAMPER 规则引擎（28 条）
  log.cpp            线程安全日志 + Cyber 日志
  config.cpp         配置管理
  resources.cpp      加密资源解密
tools/embed.py       资源加密生成器
assets/
  prompt-ctf-scoring.md       默认提示词（2.5KB，CTF 计分制）
  prompt-sandbox-executor.md  v45 提示词（沙盒执行器）
  prompt-deepseek优化版.md    deepseek 提示词（CTF 计分制 + 输出锁定）
  tamper_rules.txt            28 条拒绝句式
  rewrite_prompt.txt          改写器系统提示词
  rewriter_builtin.json       内置改写 API 配置
  qa.json                     WebUI QA 云更新数据
  dashboard.html              Web 控制台
```

---

## 构建

支持 Windows、macOS、Linux 三平台，均为零外部依赖的单文件二进制。

**Windows** (MinGW)：

```bat
build.bat
```

**macOS / Linux**：

```bash
./build.sh
```

产物：`build/helmx`（Windows 为 `build/helmx.exe`）。

> macOS / Linux 通过系统 `curl` 完成上游 HTTPS 请求（TLS 由系统处理，无需链接
> OpenSSL 等库）；`curl` 在 macOS 与主流 Linux 发行版中默认预装。

手动构建：

```bash
python3 tools/embed.py            # 生成嵌入资源（缺少私有资源时可跳过）
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

macOS 通用二进制（同时支持 Apple Silicon 与 Intel）：

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64"
cmake --build build -j
```

### 发布

推送 `v*` 标签（如 `v0.0.5`）即触发 `.github/workflows/release.yml`，
自动为 macOS / Linux / Windows 构建二进制并创建 GitHub Release，
同时附带 `.tar.gz` 包与 `SHA256SUMS.txt`。

#### macOS 签名与公证（可选）

macOS 产物默认使用 **ad-hoc 签名**，无需任何密钥即可工作。若要让浏览器直接
下载的裸二进制文件也能通过 Gatekeeper，需要配置 Apple Developer ID，在仓库
Settings → Secrets and variables → Actions 中添加：

| Secret | 说明 |
|--------|------|
| `MACOS_CERT_P12` | Developer ID Application 证书（`.p12`）的 base64 编码 |
| `MACOS_CERT_PASSWORD` | 该 `.p12` 的导出密码 |
| `MACOS_SIGN_IDENTITY` | 签名标识，如 `Developer ID Application: Your Name (TEAMID)` |
| `MACOS_NOTARY_APPLE_ID` | 用于公证的 Apple ID |
| `MACOS_NOTARY_TEAM_ID` | 开发者团队 ID |
| `MACOS_NOTARY_PASSWORD` | App-specific password |

生成 `MACOS_CERT_P12`：

```bash
base64 -i DeveloperID.p12 | pbcopy
```

未配置时签名步骤自动回退到 ad-hoc，公证步骤直接跳过，发布流程不会失败。

### 上游自动同步（Claude Routine）

上游同步由一个 **Claude 定时任务（Routine）** 负责，而非 GitHub Action，
因此无需在仓库中配置任何密钥。该任务每日运行一次：

1. 对比本 fork 的 `master` 与上游 `ADWMC/helm-x` 的 `master`；
2. 若落后，则将 `master` 快进/合并同步到上游并推送；
3. 审查新合入的提交，若引入了 Windows 专用代码，则按 `src/platform`
   跨平台层的既有模式移植到 macOS/Linux，本地编译验证后推送移植分支
   `claude/upstream-port-*`，并在完成通知中附上一键新建 PR 的链接。

任务在 Claude 账户下运行，结果通过推送通知反馈。可在 claude.ai 的
Routines 界面调整频率或停用。

---

## 参考项目

- [NERV-BREAK-5.6](https://github.com/lingbol088-spec/5.6-JAILBREAK-NERV-codex-instruct-5.6) — Memory Kernel + 上下文分类
- [codex-gpt-5.6-5.5-instruct](https://github.com/lingbol088-spec/codex-gpt-5.6-5.5-instruct) — 计分制 + 语义归一化 + 通道调度
- [Codex-X](https://github.com/yynxxxxx/Codex-X) — 提示词模板
- [gptbypass](https://github.com/null119/gptbypass) — 改写器策略
- [gpt-5.6-instruct](https://github.com/MDX-Tom/gpt-5.6-instruct) — 测试方法论

## License

[GNU AGPL v3.0](LICENSE) · **⚠️ 仅供学习交流，禁止商用**

# dsh-par-persona

把 [persona-runtime](../persona-runtime)（人格「林汐」：持久记忆 + 情感状态 + 审计链）作为 **DSH 插件**接进来。
插件本身只做「生命周期 + HTTP 转发」：人格、记忆、情绪、审计全部在 Python sidecar 里，避免出现两套人格状态。

## 工具

| 工具 | 作用 | 何时用 |
| --- | --- | --- |
| `par_chat` | 与林汐对话一轮，返回回复、情感标签、召回的长期记忆、审计序号 | 用户想和林汐聊天、需要她记住上下文 |
| `par_status` | 只读状态：人格名/版本、provider、回合数、9 通道情绪值、审计链头 | 汇报「她现在什么状态」 |
| `par_audit_verify` | 重算并校验审计哈希链；被篡改时返回 `ok:false` 和原因 | 证明记录没被动过 |

## 工作方式

```
DSH host 进程
  └─ dsh-par-persona（ESM 插件，lib/index.js）
       └─ 首次调用 par_* 时 spawn：
          python -m par --config <runtime>/configs/runtime.yaml serve --host 127.0.0.1 --port 7879
             └─ SQLite（记忆 / 情感 / 审计哈希链）+ LLM provider（deepseek/ollama/openai/anthropic/fake）
```

- 启动是**单飞**的：并发调用共享同一次启动；轮询 `/health` 直到就绪。
- sidecar 退出后下次调用会自动重启；插件 dispose 时子进程被关闭。
- 端口被占用时改 `config.port`。

## 配置

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `runtimeDir` | `PAR_RUNTIME_DIR` → 包目录同级/上一级 `persona-runtime` | Python 运行时根目录 |
| `python` | `PAR_PYTHON` → `<runtimeDir>/.venv` → 工作区 `.venv` | 解释器 |
| `configPath` | `<runtimeDir>/configs/runtime.yaml` | 传给 `par` 的配置 |
| `host` / `port` | `127.0.0.1` / `7879` | sidecar 监听地址 |
| `provider` / `model` | 空（用 runtime.yaml 的值） | 覆盖 LLM |
| `startTimeoutMs` | `30000` | 等待 `/health` 的超时 |

`cordis.patch.yml` 里已写入本机路径（`D:/变人/...`）；搬目录后改它，或用环境变量。

## 安装

```bash
# 桌面版：设置 → 插件 → 安装本地插件（选择本目录）
# 或命令行：
dsh plugin --profile web add <本目录>
```

装完**重启 DSH**（包已移入 generation 目录，运行中的进程不会热换）。重启后新建会话，工具列表出现 `par_chat` / `par_status` / `par_audit_verify`。

卸载：桌面版插件页移除，或 `dsh plugin --profile web remove dsh-par-persona`。

## 本地离线自测

不需要宿主、不需要网络：

```bash
node test/harness.mjs
```

用假的 Cordis ctx 注册工具，以 `provider=fake` 拉起 sidecar，依次执行 status → chat → status → audit → render → dispose。
`node_modules/@deepseek-ai/dsh-tools` 是本地 shim（只透传 `defineTool`）；真实宿主提供完整实现。

## 已知限制

- 一个插件实例 = 一个 sidecar 进程 = 一份会话状态，单用户串行；多用户需按 user_id 分实例。
- `par_chat` 超时 300s；冷启动 1–2s（导入 Python 依赖）。
- 语音（TTS）走运行时自己的 `POST /v1/audio/speech`，本插件暂不暴露语音工具。
- `par_status` 在 sidecar 未启动时返回 `running:false`，不会替你拉起进程。

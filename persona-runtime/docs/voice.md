# 语音模块

## 边界

语音只是**表达通道**与**感知通道**，不新增权限，也不绕开门控：

- TTS：把已经通过 `ExpressionVerifier` 的文本转成音频。文本先过校验，再朗读。
- STT：把音频转成文本后，作为 `Observation(modality="voice", trust="user")` 进入同一条 turn 流水线。

v0 只做了 TTS（Windows 内置），STT 保留接口。这是刻意的：没有麦克风链路的假实现比缺功能更糟。

## TTS

`src/par/voice/tts.py::synthesize_wav(text, rate=0, volume=100) -> bytes`

- 仅 Windows：调用 `powershell` + `System.Speech.Synthesis.SpeechSynthesizer`，输出临时 WAV 并读回。
- 非 Windows 抛 `TTSUnavailable`；HTTP 层返回 501，前端提示"本机语音不可用"。
- 文本截断 1200 字；失败清理临时文件。

```bash
curl -X POST http://127.0.0.1:7860/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"晚上好，我是林汐。"}' --output out.wav
```

语义上与 OpenAI 的 `/v1/audio/speech` 对齐（`input` 字段），方便客户端替换。

## STT

`src/par/voice/stt.py`：

| 实现 | 状态 | 说明 |
|---|---|---|
| `NullSTT` | 默认 | 抛 `STTUnavailable`，UI 降级为打字 |
| `FasterWhisperSTT` | 可选 | 需 `pip install faster-whisper`，CPU int8，VAD 开 |

接口：`transcribe(wav_path, language=None) -> str`。不返回置信度推测；识别失败必须抛错而不是编造文本。

## 为什么不接云 TTS

1. 数据出域：语音文本是对话内容，默认不出本机（对应 §14 数据治理）。
2. 依赖噪声：云 TTS 需要 key、重试、配额，v0 的收益不足以抵消这些失败面。
3. 可替换：`synthesize_wav` 是函数边界，将来接 Azure/本地 TTS 只需换实现。

## 已知限制

- **非交互上下文没有可用语音**：从服务/代理进程（例如某些 IDE 或自动化工具的沙箱子进程）启动时，SAPI 可能报"系统未安装任何语音"，`synthesize_wav` 会抛 `TTSUnavailable`，HTTP 返回 501。这不是代码缺陷，而是 Windows 语音需要交互式桌面会话。从普通终端启动 `par serve` 即可正常朗读。
- 只用手装机 voices；没有云端兜底（见下）。
- 输出为 16-bit PCM WAV，未做响度归一化。

## 测试与降级

- 单测不依赖音频设备：只测 `TTSUnavailable` 分支与 HTTP 501 形状。
- Web 页在朗读失败时弹提示，不阻塞对话。
- 语音延迟预算：SAPI 首字节通常 <500ms；长文本按 1200 字上限截断。

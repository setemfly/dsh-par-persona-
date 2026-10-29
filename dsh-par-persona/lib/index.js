/**
 * dsh-par-persona —— 把 persona-runtime（默认人格：林汐）接进 DeepSeek Harness。
 *
 * 形态：host 插件 + 本地 Python sidecar。
 *   - 首次调用 par_* 工具时，spawn `python -m par serve`（127.0.0.1，随机默认端口 7879），
 *     轮询 /health 就绪后才发请求；插件 dispose 时关掉子进程。
 *   - 三个模型工具：par_chat（对话）、par_status（状态/情绪）、par_audit_verify（审计链校验）。
 *   - 插件不复制对话状态机：记忆、情感、审计、人格卡全部由 Python 运行时负责，
 *     插件只做生命周期 + HTTP 转发，避免出现"两套人格"。
 *
 * 配置（都可通过 cordis.patch.yml 的 config 覆盖）：
 *   runtimeDir   persona-runtime 根目录；默认 = 插件目录的兄弟目录 persona-runtime
 *   python       Python 解释器；默认 = <runtimeDir>/.venv/Scripts/python.exe（Windows）
 *                或 <runtimeDir>/.venv/bin/python（POSIX），最后回退 "python"
 *   configPath   par 配置文件；默认 <runtimeDir>/configs/runtime.yaml
 *   host/port    sidecar 监听地址；默认 127.0.0.1:7879
 *   provider     可选，透传 `par serve --provider`
 *   model        可选，透传 `par serve --model`
 *   startTimeoutMs  等待 /health 的超时；默认 30000
 */

import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineTool } from '@deepseek-ai/dsh-tools'

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

export const name = 'par-persona'
/** 只依赖工具注册表；Python sidecar 自己管理进程，不占用其他宿主服务。 */
export const inject = ['tools']

const DEFAULT_PORT = 7879

function firstExisting(candidates) {
  for (const candidate of candidates) {
    try {
      if (candidate && fs.existsSync(candidate)) return candidate
    } catch {
      // ignore unreadable candidates
    }
  }
  return undefined
}

/**
 * Resolve every path the sidecar needs, with the same precedence the README documents.
 *
 * A linked plugin sits next to `persona-runtime/`, but an installed plugin lives
 * under the profile's generation directory. When neither the config nor
 * `PAR_RUNTIME_DIR` names the runtime, look one and two levels above the package
 * before falling back to the sibling convention.
 */
function resolveSettings(config) {
  const explicit = config?.runtimeDir || process.env.PAR_RUNTIME_DIR
  const runtimeDir = path.resolve(
    explicit ||
      firstExisting([
        path.join(PACKAGE_ROOT, '..', 'persona-runtime'),
        path.join(PACKAGE_ROOT, '..', '..', 'persona-runtime'),
      ]) ||
      path.join(PACKAGE_ROOT, '..', 'persona-runtime'),
  )
  const python =
    config?.python ||
    process.env.PAR_PYTHON ||
    firstExisting([
      path.join(runtimeDir, '.venv', 'Scripts', 'python.exe'),
      path.join(runtimeDir, '.venv', 'bin', 'python'),
      // A workspace-level venv beside the runtime (the common local layout).
      path.join(runtimeDir, '..', '.venv', 'Scripts', 'python.exe'),
      path.join(runtimeDir, '..', '.venv', 'bin', 'python'),
    ]) ||
    'python'
  return {
    runtimeDir,
    python,
    configPath: config?.configPath || path.join(runtimeDir, 'configs', 'runtime.yaml'),
    host: config?.host || '127.0.0.1',
    port: Number(config?.port) || DEFAULT_PORT,
    provider: config?.provider || '',
    model: config?.model || '',
    startTimeoutMs: Number(config?.startTimeoutMs) || 30000,
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * The sidecar client. One instance per plugin application:
 * single-flight start, bounded stderr ring for diagnostics, idempotent dispose.
 */
class ParSidecar {
  constructor(settings) {
    this.settings = settings
    this.baseUrl = `http://${settings.host}:${settings.port}`
    this.child = undefined
    this.starting = undefined
    this.stderr = []
    this.disposed = false
  }

  get running() {
    return Boolean(this.child && this.child.exitCode === null && !this.child.killed)
  }

  async health(timeoutMs = 1500) {
    try {
      const res = await fetch(`${this.baseUrl}/health`, { signal: AbortSignal.timeout(timeoutMs) })
      if (!res.ok) return undefined
      return await res.json()
    } catch {
      return undefined
    }
  }

  /** Start the sidecar if it is not healthy yet; concurrent callers share one start. */
  async ensure() {
    if (this.disposed) throw new Error('par-persona: plugin is disposed')
    if (await this.health(800)) return
    if (this.starting) return this.starting
    this.starting = this.#start().finally(() => {
      this.starting = undefined
    })
    return this.starting
  }

  async #start() {
    const { runtimeDir, python, configPath, host, port, provider, model, startTimeoutMs } = this.settings
    if (!fs.existsSync(runtimeDir)) {
      throw new Error(`par-persona: runtimeDir not found: ${runtimeDir}`)
    }
    if (!fs.existsSync(configPath)) {
      throw new Error(`par-persona: config not found: ${configPath}`)
    }
    // `--config` is a top-level flag on the `par` CLI, so it must precede the subcommand.
    const args = ['-m', 'par', '--config', configPath, 'serve', '--host', host, '--port', String(port)]
    if (provider) args.push('--provider', provider)
    if (model) args.push('--model', model)
    const env = {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      PYTHONPATH: [path.join(runtimeDir, 'src'), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
    }
    this.stderr = []
    const child = spawn(python, args, { cwd: runtimeDir, env, windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] })
    this.child = child
    const record = (chunk) => {
      for (const line of String(chunk).split(/\r?\n/)) {
        const text = line.trim()
        if (!text) continue
        this.stderr.push(text)
        if (this.stderr.length > 40) this.stderr.shift()
      }
    }
    child.stderr?.on('data', record)
    child.once('exit', (code, signal) => {
      record(`[sidecar exited code=${code ?? 'null'} signal=${signal ?? 'null'}]`)
    })
    const deadline = Date.now() + startTimeoutMs
    while (Date.now() < deadline) {
      if (await this.health(800)) return
      if (child.exitCode !== null) break
      await sleep(300)
    }
    throw new Error(
      `par-persona: sidecar did not become healthy at ${this.baseUrl} (python=${python}, runtimeDir=${runtimeDir}). ` +
        `Last stderr:\n${this.stderr.slice(-12).join('\n') || '(empty)'}`,
    )
  }

  async #request(pathname, init) {
    await this.ensure()
    const res = await fetch(`${this.baseUrl}${pathname}`, {
      ...init,
      signal: AbortSignal.timeout(init?.timeoutMs ?? 180000),
    })
    const text = await res.text()
    let body
    try {
      body = text ? JSON.parse(text) : {}
    } catch {
      body = { raw: text.slice(0, 500) }
    }
    if (!res.ok && !(typeof body === 'object' && body && 'ok' in body)) {
      throw new Error(`par-persona: ${pathname} -> HTTP ${res.status}: ${JSON.stringify(body).slice(0, 300)}`)
    }
    return body
  }

  async chat(message) {
    const body = await this.#request('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ message }),
      timeoutMs: 300000,
    })
    return body
  }

  async state() {
    return this.#request('/api/state', { timeoutMs: 10000 })
  }

  async auditVerify() {
    return this.#request('/api/audit/verify', { timeoutMs: 30000 })
  }

  async tools() {
    return this.#request('/api/tools', { timeoutMs: 10000 })
  }

  async dispose() {
    this.disposed = true
    const child = this.child
    this.child = undefined
    if (!child || child.exitCode !== null) return
    child.kill()
    await new Promise((resolve) => {
      const timer = setTimeout(resolve, 3000)
      child.once('exit', () => {
        clearTimeout(timer)
        resolve()
      })
    })
  }
}

function labelLines(labels) {
  const entries = Object.entries(labels || {}).sort((a, b) => b[1] - a[1])
  return entries.map(([key, value]) => `${key}=${Number(value).toFixed(2)}`).join(' ')
}

function formatChat(value) {
  const lines = [value.reply]
  if (value.labels?.length) lines.push('', `[affect] ${value.labels.join(' ')}`)
  const pipeline = [`intent=${value.intent || 'chat'}`, `gate=${value.gate || '(none)'}`]
  if (value.executed?.length) {
    pipeline.push(`steps=${value.executed.map((s) => `${s.step_id}:${s.status}`).join(',')}`)
  }
  if (value.deviation) pipeline.push(`deviation=${value.deviation}`)
  lines.push('', `[pipeline] ${pipeline.join(' ')}`)
  if (value.memories?.length) {
    lines.push('', '[recall]')
    for (const memory of value.memories.slice(0, 5)) lines.push(`- (${memory.kind}) ${memory.text}`)
  }
  lines.push('', `[audit] seq=${value.audit_seq} verifier=${value.verifier_ok ? 'ok' : 'issues'}`)
  return lines.join('\n')
}

function formatStatus(value) {
  if (!value.running) return `par-persona: sidecar not running (${value.error || 'not started'})`
  return [
    `par-persona: ${value.persona} v${value.version}`,
    `agent=${value.agent_id} provider=${value.provider} turns=${value.turns}`,
    `labels: ${value.labels?.length ? value.labels.join(' ') : '(none)'}`,
    `audit: seq=${value.audit_seq} hash=${String(value.audit_hash || '').slice(0, 12)}…`,
  ].join('\n')
}

export function apply(ctx, config = {}) {
  const settings = resolveSettings(config)
  const sidecar = new ParSidecar(settings)
  ctx.on?.('dispose', () => sidecar.dispose())

  ctx.tools.register(
    defineTool({
      name: 'par_chat',
      description:
        '与常驻人格「林汐」对话（persona-runtime）。适合角色化闲聊、情绪陪伴、需要长期记忆延续的对话；' +
        '不适合当通用任务代理或代替普通文件/命令工具。首次调用会自动启动本地 Python sidecar（可能需要几秒）。',
      parameters: {
        message: { type: 'string', required: true, description: '发给林汐的消息原文' },
      },
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            reply: { type: 'string', required: true },
            labels: { type: 'array', items: { type: 'string' } },
            intent: { type: 'string' },
            gate: { type: 'string' },
            deviation: { type: 'string' },
            executed: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                properties: { step_id: { type: 'string' }, status: { type: 'string' } },
              },
            },
            memories: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                properties: { text: { type: 'string' }, kind: { type: 'string' } },
              },
            },
            audit_seq: { type: 'integer' },
            verifier_ok: { type: 'boolean' },
          },
        },
        render: (_args, value) => [{ type: 'text', text: formatChat(value) }],
      },
      timeoutMs: 300000,
      async execute(args) {
        const raw = await sidecar.chat(String(args.message || '').trim())
        return {
          reply: String(raw.reply || ''),
          labels: Object.entries(raw.labels || {}).map(([k, v]) => `${k}=${Number(v).toFixed(2)}`),
          intent: String(raw.intent || 'chat'),
          gate: raw.gate_verdict == null ? undefined : String(raw.gate_verdict),
          deviation: raw.deviation == null ? undefined : String(raw.deviation),
          executed: (raw.executed || []).map((s) => ({ step_id: String(s.step_id || ''), status: String(s.status || '') })),
          memories: (raw.memories || []).slice(0, 5).map((m) => ({ text: String(m.text || ''), kind: String(m.kind || '') })),
          audit_seq: Number(raw.audit_seq || 0),
          verifier_ok: Boolean(raw.verifier_ok),
        }
      },
    }),
  )

  ctx.tools.register(
    defineTool({
      name: 'par_status',
      description: '读取林汐当前的人格版本、情绪通道、对话轮数与审计链头（只读；不会启动 sidecar）。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            running: { type: 'boolean' },
            error: { type: 'string' },
            agent_id: { type: 'string' },
            persona: { type: 'string' },
            version: { type: 'string' },
            provider: { type: 'string' },
            turns: { type: 'integer' },
            labels: { type: 'array', items: { type: 'string' } },
            audit_seq: { type: 'integer' },
            audit_hash: { type: 'string' },
          },
        },
        render: (_args, value) => [{ type: 'text', text: formatStatus(value) }],
      },
      isConcurrencySafe: () => true,
      async execute() {
        if (!(await sidecar.health(800))) {
          return { running: false, error: 'sidecar not running; call par_chat to start it' }
        }
        const state = await sidecar.state()
        return {
          running: true,
          agent_id: String(state.agent_id || ''),
          persona: String(state.persona || ''),
          version: String(state.version || ''),
          provider: String(state.provider || ''),
          turns: Number(state.turns || 0),
          labels: Object.entries(state.labels || {})
            .sort((a, b) => b[1] - a[1])
            .map(([k, v]) => `${k}=${Number(v).toFixed(2)}`),
          audit_seq: Number(state.audit_head?.seq || 0),
          audit_hash: String(state.audit_head?.hash || ''),
        }
      },
    }),
  )

  ctx.tools.register(
    defineTool({
      name: 'par_tools',
      description: '列出林汐运行时当前可用的内置工具及其副作用等级（只读）。用于判断哪类请求（时间/算术/读工作区文件）会被规划成真实工具调用。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            tools: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                properties: {
                  name: { type: 'string' },
                  side_effect: { type: 'string' },
                  requires_approval: { type: 'boolean' },
                },
              },
            },
          },
        },
        render: (_args, value) => [
          {
            type: 'text',
            text: value.tools.length
              ? value.tools.map((t) => `- ${t.name} (${t.side_effect}${t.requires_approval ? ', needs approval' : ''})`).join('\\n')
              : 'par-persona: no tools registered',
          },
        ],
      },
      isConcurrencySafe: () => true,
      async execute() {
        if (!(await sidecar.health(800))) await sidecar.ensure()
        const body = await sidecar.tools()
        return {
          tools: (body.tools || []).map((t) => ({
            name: String(t.name || ''),
            side_effect: String(t.side_effect || 'none'),
            requires_approval: Boolean(t.requires_approval),
          })),
        }
      },
    }),
  )

  ctx.tools.register(
    defineTool({
      name: 'par_audit_verify',
      description: '重算林汐审计库的哈希链并校验前向链接；篡改会返回 ok=false 与原因（只读）。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            ok: { type: 'boolean' },
            audit_seq: { type: 'integer' },
            audit_hash: { type: 'string' },
            error: { type: 'string' },
          },
        },
        render: (_args, value) => [
          {
            type: 'text',
            text: value.ok
              ? `audit chain ok: seq=${value.audit_seq} head=${String(value.audit_hash).slice(0, 12)}…`
              : `audit chain broken: ${value.error || 'unknown'}`,
          },
        ],
      },
      isConcurrencySafe: () => true,
      async execute() {
        if (!(await sidecar.health(800))) await sidecar.ensure()
        const body = await sidecar.auditVerify()
        return {
          ok: Boolean(body.ok),
          audit_seq: Number(body.head?.seq || 0),
          audit_hash: String(body.head?.hash || ''),
          error: body.ok ? undefined : String(body.detail || body.error || ''),
        }
      },
    }),
  )

  ctx.logger?.info?.(`par-persona ready (runtimeDir=${settings.runtimeDir}, port=${settings.port})`)
}

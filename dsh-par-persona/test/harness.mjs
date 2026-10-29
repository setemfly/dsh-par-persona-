/**
 * Offline harness for dsh-par-persona.
 *
 * Runs the plugin against a fake Cordis context: registers the tools, starts the
 * real Python sidecar (provider=fake), exercises every tool, then disposes.
 *
 *   node test/harness.mjs
 */
import { apply } from '../lib/index.js'

const tools = new Map()
const disposers = []
const ctx = {
  tools: { register: (tool) => tools.set(tool.name, tool) },
  on: (event, fn) => { if (event === 'dispose') disposers.push(fn) },
  logger: console,
}

apply(ctx, {
  runtimeDir: 'D:/变人/persona-runtime',
  python: 'D:/变人/.venv/Scripts/python.exe',
  port: 7889,
  provider: 'fake',
})

const names = [...tools.keys()]
console.log('registered:', names.join(', '))

const status0 = await tools.get('par_status').execute({}, {})
console.log('status(before):', JSON.stringify(status0))

const chat = await tools.get('par_chat').execute({ message: '你好，我叫阿羽，喜欢拿铁' }, {})
console.log('chat.reply:', chat.reply)
console.log('chat.labels:', chat.labels.join(' '), 'audit_seq=', chat.audit_seq, 'verifier=', chat.verifier_ok)

const status1 = await tools.get('par_status').execute({}, {})
console.log('status(after):', JSON.stringify({ turns: status1.turns, persona: status1.persona, v: status1.version, audit_seq: status1.audit_seq }))

const audit = await tools.get('par_audit_verify').execute({}, {})
console.log('audit:', JSON.stringify(audit))

const renderedTools = tools.get('par_chat').output.render({}, chat)
console.log('--- rendered par_chat ---')
console.log(renderedTools[0].text)

const t = await tools.get('par_tools').execute({}, {})
console.log('--- par_tools ---')
console.log(t.tools.map((x) => `${x.name}(${x.side_effect})`).join(', '))
const pipeline = tools
  .get('par_chat')
  .output.render({}, { ...chat, intent: 'time', gate: 'allow', executed: [{ step_id: 's1', status: 'ok' }] })[0]
  .text.split(String.fromCharCode(10))
  .find((line) => line.startsWith('[pipeline]'))
console.log('--- pipeline ---')
console.log(pipeline)

for (const dispose of disposers) await dispose()
console.log('disposed')

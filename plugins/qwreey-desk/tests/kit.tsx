// What the desk's tests share: hooks that stand for the engine beneath the
// plugin (store, clock, session, prompt, render), and a project folder in
// memory with git's few commands the desk runs.

import { mock } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'

export const TOOL = 'mcp__qwreey-desk__desk'
export const ROOT = '/p'
export const STORE_KEY = `project:${ROOT}`

export type Submitted = { text: string; context?: readonly string[] }

// Nothing sits beneath the plugin: these hooks stand for the engine.
export const engine = (on: On, store: Record<string, unknown> = {}) => {
  const clock = mock.clock(on, { now: 1_000_000 })
  // The store in memory, kept here so a test reads what the plugin wrote.
  const kept = new Map<string, unknown>(Object.entries(store))
  // Every write the desk makes, the store's counted and the session state's by key.
  const writes = { store: 0, state: [] as string[] }
  on('store.get', (_, e) => ({ value: kept.get(e.key) }))
  on('store.set', (_, e) => {
    writes.store += 1
    kept.set(e.key, JSON.parse(JSON.stringify(e.value)))
    return { value: undefined }
  })
  // The session's desk as the plugin last set it.
  let session: unknown
  on('state.set', (_, e, next) => {
    writes.state.push(e.key)
    if (e.key === 'data') session = e.value
    return next(e)
  })
  const held = () => {
    const v = session as { shape?: string; value?: any } | undefined
    return v && typeof v === 'object' && 'shape' in v ? v.value : (v as any)
  }
  // What the desk last persisted for /p (it mirrors the session's state).
  const stored = () => (kept.get(STORE_KEY) as { shape: string; value: any } | undefined)?.value
  const submitted: Submitted[] = []
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: ROOT }))
  on('tool.register', () => ({ value: { tool: TOOL } }))
  on('command.register', () => ({ value: { command: 'desk' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('prompt.submit', (_, e) => {
    submitted.push({ text: e.text, context: e.context })
    return { text: e.text, context: e.context }
  })
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  return { clock, submitted, kept, stored, writes, held }
}

export const start = ($: Engine) => $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })

export const desk = (input: Record<string, unknown>) => ({ tool: TOOL, ...input }) as Parameters<Engine['tool']['call']>[0]

const ran = (exitCode: number, stdout = '', stderr = '') => ({ value: { exitCode, stdout, stderr, isStdoutTruncated: false, isStderrTruncated: false } })

/**
 * A project folder in memory under ROOT, answering the desk's file calls and
 * the commands it runs: `git rev-parse` (a work tree or not), `git ls-files
 * --error-unmatch`, `git mv`, `mv`, `mkdir -p`. `tracked` is what git tracks.
 */
export const repo = (on: On, { isGit = true, files = {} as Record<string, string> } = {}) => {
  let tick = 1
  const kept = new Map<string, { text: string; mtimeMs: number }>()
  const tracked = new Set<string>()
  const runs: string[][] = []
  const written: string[] = []
  const put = (path: string, text: string) => {
    tick += 1
    kept.set(path, { text, mtimeMs: tick })
  }
  for (const [path, text] of Object.entries(files)) put(`${ROOT}/${path}`, text)
  const absOf = (cwd: string | undefined, path: string) => (path.startsWith('/') ? path : `${cwd ?? ROOT}/${path}`)
  const move = (from: string, to: string) => {
    const f = kept.get(from)
    if (!f) return false
    kept.delete(from)
    put(to, f.text)
    return true
  }
  on('fs.read', (_, e) => {
    const f = kept.get(e.path)
    if (!f) throw new Error(`ENOENT: ${e.path}`)
    return { value: f.text }
  })
  on('fs.write', (_, e) => {
    written.push(e.path)
    put(e.path, e.text)
    return { value: undefined }
  })
  on('fs.exists', (_, e) => ({ value: kept.has(e.path) || [...kept.keys()].some(k => k.startsWith(`${e.path}/`)) }))
  on('fs.stat', (_, e) => {
    const f = kept.get(e.path)
    if (!f) throw new Error(`ENOENT: ${e.path}`)
    return { value: { kind: 'file' as const, size: f.text.length, mtimeMs: f.mtimeMs, isLink: false } }
  })
  on('fs.list', (_, e) => {
    const prefix = `${e.path}/`
    const names = new Map<string, { kind: 'file' | 'dir'; size: number; mtimeMs: number }>()
    for (const [path, f] of kept) {
      if (!path.startsWith(prefix)) continue
      const [name = '', ...deeper] = path.slice(prefix.length).split('/')
      names.set(name, deeper.length > 0 ? { kind: 'dir', size: 0, mtimeMs: 0 } : { kind: 'file', size: f.text.length, mtimeMs: f.mtimeMs })
    }
    // A folder not there lists as empty here; the desk reads it so either way.
    return { value: [...names].map(([name, s]) => ({ name, ...s, isLink: false })) }
  })
  on('process.run', (_, e) => {
    const argv = [...e.argv]
    runs.push(argv)
    const cwd = e.init?.cwd
    const args = argv.filter(a => a !== '--')
    if (args[0] === 'git' && args[1] === 'rev-parse') return isGit ? ran(0, 'true\n') : ran(128, '', 'fatal: not a git repository')
    if (!isGit && args[0] === 'git') return ran(128, '', 'fatal: not a git repository')
    if (args[0] === 'mkdir') return ran(0)
    if (args[0] === 'git' && args[1] === 'ls-files') return ran(tracked.has(args[3] ?? '') ? 0 : 1)
    if (args[0] === 'git' && args[1] === 'mv') {
      const [from = '', to = ''] = args.slice(2)
      if (!tracked.has(from) || kept.has(absOf(cwd, to))) return ran(128, '', 'fatal: bad source or destination')
      move(absOf(cwd, from), absOf(cwd, to))
      tracked.delete(from)
      tracked.add(to)
      return ran(0)
    }
    if (args[0] === 'mv') return ran(move(absOf(cwd, args[1] ?? ''), absOf(cwd, args[2] ?? '')) ? 0 : 1)
    return ran(127, '', `not faked: ${argv.join(' ')}`)
  })
  const text = (path: string) => kept.get(`${ROOT}/${path}`)?.text
  /** The names in a folder of the project, sorted. */
  const names = (dir: string) =>
    [...kept.keys()]
      .filter(k => k.startsWith(`${ROOT}/${dir}/`) && !k.slice(`${ROOT}/${dir}/`.length).includes('/'))
      .map(k => k.slice(`${ROOT}/${dir}/`.length))
      .sort()
  /** Changes a file as another session or a git pull would. */
  const edit = (path: string, text: string) => put(`${ROOT}/${path}`, text)
  return { runs, written, tracked, text, names, edit, move: (from: string, to: string) => move(`${ROOT}/${from}`, `${ROOT}/${to}`) }
}

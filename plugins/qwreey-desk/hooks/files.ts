// The desk's files in the project folder: finding whether there is one to
// write, reading the decisions and the plan back (a file read again only
// when its size or time changed), writing what changed, and moving an
// answered decision to the archive, with git when git tracks it. The desk
// never commits: what it writes goes into the next commit with the rest.

import type { EngineInterface, FsEntry } from 'claude-code'

import type { DeskData, DeskDecision, DeskStep } from '../types'
import { DONE_DIR, OPEN_DIR, PLAN_DIR, PLAN_FILE, PLAN_README, README_TEXT, decisionText, fileFor, parseDecision, parsePlan, planText } from './records'

type $ = EngineInterface

const RUN_MS = 10_000

// Said once in the band when the desk keeps everything in the store.
export const NO_GIT = '책상 파일 없음: git 저장소가 아님, 이 컴퓨터에만 저장'
export const NO_PROCESS = '책상 파일 없음: git 을 못 돌림, 이 컴퓨터에만 저장'
export const NOT_WRITTEN = '책상 파일 못 씀: 이 컴퓨터에만 저장'

/** The project folder the files go under, or why there is none. */
export async function findRoot($: $, cwd: string): Promise<{ root?: string; reason?: string }> {
  const ran = await $.process.run(['git', 'rev-parse', '--is-inside-work-tree'], { cwd, timeoutMs: RUN_MS }).catch(() => undefined)
  if (!ran || typeof ran.exitCode !== 'number') return { reason: NO_PROCESS }
  return ran.exitCode === 0 && ran.stdout.trim() === 'true' ? { root: cwd } : { reason: NO_GIT }
}

// Each file read, by its absolute path, with the size and time it had: the
// pane re-reads the folders often, and a file unchanged is not read again.
// A cache only: a reload empties it and the next read fills it.
const seen = new Map<string, { size: number; mtimeMs: number; value: unknown }>()

const abs = (root: string, rel: string) => `${root}/${rel}`

function listed($: $, dir: string): Promise<readonly FsEntry[]> {
  return $.fs.list(dir).then(
    entries => (Array.isArray(entries) ? entries : []),
    () => [],
  )
}

async function readCached<T>($: $, path: string, entry: FsEntry, parse: (text: string) => T): Promise<T | undefined> {
  const hit = seen.get(path)
  if (hit && hit.size === entry.size && hit.mtimeMs === entry.mtimeMs) return hit.value as T
  const text = await $.fs.read(path).catch(() => undefined)
  if (typeof text !== 'string') return undefined
  const value = parse(text)
  seen.set(path, { size: entry.size, mtimeMs: entry.mtimeMs, value })
  return value
}

async function remember($: $, path: string, value: unknown) {
  const stat = await $.fs.stat(path).catch(() => undefined)
  if (stat) seen.set(path, { size: stat.size, mtimeMs: stat.mtimeMs, value })
  else seen.delete(path)
}

const DECISION_FILE = /^[DQ]\d+\b.*\.md$/i

export type Files = { decisions: DeskDecision[]; plan?: DeskStep[] }

/** The decisions in both folders (an archived one over an open one of the same id) and the plan, absent with no plan file. */
export async function readFiles($: $, root: string): Promise<Files> {
  const found = new Map<string, DeskDecision>()
  for (const dir of [OPEN_DIR, DONE_DIR]) {
    for (const entry of await listed($, abs(root, dir))) {
      if (entry.kind !== 'file' || !DECISION_FILE.test(entry.name)) continue
      const rel = `${dir}/${entry.name}`
      const d = await readCached($, abs(root, rel), entry, text => parseDecision(text, rel))
      if (d) found.set(d.id, d)
    }
  }
  const name = PLAN_FILE.slice(PLAN_DIR.length + 1)
  const entry = (await listed($, abs(root, PLAN_DIR))).find(e => e.kind === 'file' && e.name === name)
  const plan = entry ? await readCached($, abs(root, PLAN_FILE), entry, parsePlan) : undefined
  return { decisions: [...found.values()], ...(plan ? { plan } : {}) }
}

function run($: $, root: string, argv: readonly string[]) {
  return $.process.run(argv, { cwd: root, timeoutMs: RUN_MS }).catch(() => ({ exitCode: 1, stdout: '', stderr: '' }))
}

/**
 * Moves a file within the project: `git mv` when git tracks it, so the
 * history follows, else a plain `mv`. Nothing is deleted: a move that fails
 * leaves the old file where it was.
 */
async function moveFile($: $, root: string, from: string, to: string) {
  await run($, root, ['mkdir', '-p', '--', to.slice(0, to.lastIndexOf('/'))])
  const isTracked = (await run($, root, ['git', 'ls-files', '--error-unmatch', '--', from])).exitCode === 0
  await run($, root, isTracked ? ['git', 'mv', '--', from, to] : ['mv', '--', from, to])
  seen.delete(abs(root, from))
}

const readmes = new Set<string>()

async function ensureReadme($: $, root: string) {
  if (readmes.has(root)) return
  if (!(await $.fs.exists(abs(root, PLAN_README)))) await $.fs.write(abs(root, PLAN_README), README_TEXT)
  readmes.add(root)
}

/** Writes a decision to its `file`, first moving it there from `from` when it lived elsewhere. */
async function writeDecision($: $, root: string, d: DeskDecision, from?: string) {
  const to = d.file ?? fileFor(d)
  await ensureReadme($, root)
  if (from && from !== to && (await $.fs.exists(abs(root, from)))) await moveFile($, root, from, to)
  const text = decisionText(d)
  await $.fs.write(abs(root, to), text)
  await remember($, abs(root, to), parseDecision(text, to))
}

async function writePlan($: $, root: string, plan: readonly DeskStep[]) {
  await ensureReadme($, root)
  const text = planText(plan)
  await $.fs.write(abs(root, PLAN_FILE), text)
  await remember($, abs(root, PLAN_FILE), parsePlan(text))
}

/** Each decision with the file it belongs in now, by its status: the same value where nothing moves. */
export const placed = (data: DeskData): DeskData => {
  const decisions = data.decisions.map(d => {
    const file = fileFor(d)
    return file === d.file ? d : { ...d, file }
  })
  return decisions.every((d, i) => d === data.decisions[i]) ? data : { ...data, decisions }
}

/** Writes the files a change touched: each decision whose file text or place changed, and the plan. True when any was written. */
export async function saveFiles($: $, root: string, before: DeskData, after: DeskData): Promise<boolean> {
  let wrote = false
  for (const d of after.decisions) {
    const old = before.decisions.find(o => o.id === d.id)
    if (old === d) continue
    if (old && old.file === d.file && decisionText(old) === decisionText(d)) continue
    await writeDecision($, root, d, old?.file)
    wrote = true
  }
  if (planText(before.plan) !== planText(after.plan)) {
    await writePlan($, root, after.plan)
    wrote = true
  }
  return wrote
}

/**
 * Writes what the store held and the files do not yet: decisions of a
 * desk-1 value, or of a folder that had no files before, each under its
 * Q name (an answered one straight into the archive), and the plan when
 * there is no plan file. A decision whose id has a file already is left as
 * it is, so running this again writes nothing.
 */
export async function carryOver($: $, root: string, held: DeskData): Promise<number> {
  const files = await readFiles($, root)
  const have = new Set(files.decisions.map(d => d.id))
  let count = 0
  for (const d of held.decisions) {
    if (have.has(d.id)) continue
    const { file: _f, ...rest } = d
    await writeDecision($, root, { ...rest, file: fileFor(rest) })
    count += 1
  }
  if (held.plan.length > 0 && !files.plan) {
    await writePlan($, root, held.plan)
    count += 1
  }
  return count
}

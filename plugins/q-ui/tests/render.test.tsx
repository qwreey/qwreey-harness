import { expect, test } from 'claude-code/testing'
import { parseHint } from '../hooks/hint'

const MODE = (modes: string[]) =>
  ({ plugin: 'q-ui', component: 'SessionMode', requestId: 'mode', props: { modes } }) as const

const HINT = (props: Record<string, unknown>) =>
  ({ plugin: 'q-ui', component: 'PromptHint', requestId: 'hint', props: { isDraft: false, isWorking: false, hint: '', ...props } }) as const

const IDLE = 'auto mode on (shift+tab to cycle) · ← 1 agent'

const writes: Record<string, string> = {}

const stubEngine = (on: any, extra: { style?: string } = {}) => {
  on('session.id', () => ({ value: 'sid1' }))
  on('fs.write', (_: any, e: any) => {
    writes[e.path] = e.text
    return { value: null }
  })
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('session.model', () => ({ value: 'claude-opus-5-5' }))
  on('session.usage', () => ({
    value: {
      startedAt: 0,
      context: { window: 200000, percent: 30 },
      rateLimits: [
        { kind: 'five_hour', percentUsed: 12, resetsAt: new Date(Date.now() + 2.02 * 3600e3).toISOString() },
        { kind: 'seven_day', percentUsed: 31 },
      ],
      cost: { usd: 12.34 },
    },
  }))
  on('process.run', (_: any, e: any) => ({
    value: { exitCode: 0, stdout: e.argv[1] === 'status' ? ' M x\n' : 'main\n', stderr: '' },
  }))
  on('env.get', (_: any, e: any) => ({
    value: e.name === 'HARNESS_STATUSLINE_STYLE' ? extra.style : e.name === 'TMPDIR' ? '/tmp/t' : '/home/x',
  }))
  on('fs.read', () => ({ deny: 'test: no file' }))
  on('clock.every', () => ({ value: null }))
  // 엔진 자리: q-ui 가 지나가게 두면 엔진이 힌트(+ q-ui 가 붙인 tail)를 이렇게 그린다.
  on('ui.render', ($: any, e: any) => {
    const { Text } = $.ui.resolve(e)
    return <Text>{[e.props.hint, e.props.tail].filter(Boolean).join(' ')}</Text>
  })
}

const start = ($: any) => $.session.start({ cwd: '/work/claude-doctor', surface: 'terminal', isInteractive: true })
const textOf = async (ui: any) => (await ui.findAll({ type: 'Text' })).map((t: any) => t.text).join('')

test('parseHint: 모드·알약·한가함', () => {
  expect(parseHint(IDLE)).toEqual({ mode: 'auto', agents: 1, idle: true })
  expect(parseHint('plan mode on (shift+tab to cycle)')).toEqual({ mode: 'plan', agents: 0, idle: true })
  expect(parseHint('? for shortcuts')).toEqual({ mode: '', agents: 0, idle: true })
  expect(parseHint('esc to interrupt').idle).toBe(false)
  expect(parseHint('esc to interrupt · ← 2 agents')).toMatchObject({ agents: 2, idle: false })
})

test('PromptHint merge: 한가하면 모드 · 묶음 · N agents 한 줄', { options: { site: 'prompt-hint', hint: 'merge', style: 'plain' } }, async ($, on) => {
  stubEngine(on)
  await start($)
  const ui = await $.ui.mount({ ...HINT({ hint: IDLE }), surface: 'terminal' })
  expect(await textOf(ui)).toBe(
    'auto · claude-doctor:main* · Opus 5.5 ctx 30% · limit 5h 12% wk 31% reset 2h01m · $12.34 · 1 agent',
  )
  await ui.unmount()
})

test('PromptHint merge nerd: 묶음 │, 앞뒤는 ·', { options: { site: 'prompt-hint', hint: 'merge', style: 'nerd' } }, async ($, on) => {
  stubEngine(on)
  await start($)
  const ui = await $.ui.mount({ ...HINT({ hint: 'auto mode on (shift+tab to cycle) · ← 3 agents' }), surface: 'terminal' })
  const t = await textOf(ui)
  expect(t.startsWith('auto · ')).toBe(true)
  expect(t).toContain(' │ $12.34 · 3 agents')
  await ui.unmount()
})

test('PromptHint merge: 좁은 폭은 뒤 묶음부터 빼고 agents 는 남긴다', { options: { site: 'prompt-hint', hint: 'merge', style: 'plain' } }, async ($, on) => {
  stubEngine(on)
  await start($)
  const ui = await $.ui.mount({ ...HINT({ hint: IDLE }), surface: 'terminal', viewport: { columns: 50, rows: 20 } })
  const t = await textOf(ui)
  expect(t.startsWith('auto · claude-doctor:main*')).toBe(true)
  expect(t.endsWith(' · 1 agent')).toBe(true)
  expect(t.length).toBeLessThanOrEqual(46)
  expect(t).not.toContain('$12.34')
  await ui.unmount()
})

test('PromptHint merge: 작업 중이면 엔진 힌트를 살리고 tail 만 덧붙인다', { options: { site: 'prompt-hint', hint: 'merge', style: 'plain' } }, async ($, on) => {
  stubEngine(on)
  await start($)
  const ui = await $.ui.mount({ ...HINT({ hint: 'esc to interrupt', isWorking: true }), surface: 'terminal' })
  // 엔진이 그리는 줄이므로 q-ui 가 직접 그린 트리는 없다. tail 이 들어갔는지는 엔진 줄 글자로 본다.
  const t = await textOf(ui)
  expect(t).toContain('esc to interrupt')
  expect(t).toContain('claude-doctor:main*')
  await ui.unmount()
})

test('PromptHint merge: 권한 대기 같은 모르는 문구도 엔진 힌트를 살린다', { options: { site: 'prompt-hint', hint: 'merge', style: 'plain' } }, async ($, on) => {
  stubEngine(on)
  await start($)
  const ui = await $.ui.mount({ ...HINT({ hint: 'Esc to cancel · Tab to amend' }), surface: 'terminal' })
  expect(await textOf(ui)).toContain('Esc to cancel · Tab to amend')
  await ui.unmount()
})

test('PromptHint keep: 엔진 줄 그대로 + tail', { options: { site: 'prompt-hint', hint: 'keep', style: 'plain' } }, async ($, on) => {
  stubEngine(on)
  await start($)
  const ui = await $.ui.mount({ ...HINT({ hint: IDLE }), surface: 'terminal' })
  const t = await textOf(ui)
  expect(t).toContain(IDLE)
  expect(t).toContain('Opus 5.5')
  await ui.unmount()
})

test('SessionMode: 기본(prompt-hint)에서는 엔진 원래 표시(중복 없음)', async ($, on) => {
  stubEngine(on)
  await start($)
  const ui = await $.ui.mount({ ...MODE(['focus']), surface: 'terminal' })
  expect(await textOf(ui)).not.toContain('Opus')
  await ui.unmount()
})

test('SessionMode: site=session-mode 는 이전처럼 오른쪽에 그린다', { options: { site: 'session-mode', style: 'plain' } }, async ($, on) => {
  stubEngine(on)
  await start($)
  const ui = await $.ui.mount({ ...MODE(['auto']), surface: 'terminal' })
  expect(await textOf(ui)).toBe(
    'auto · claude-doctor:main* · Opus 5.5 ctx 30% · limit 5h 12% wk 31% reset 2h01m · $12.34',
  )
  await ui.unmount()
})

test('표지 파일: 켜지면 TMPDIR/claude-subagent-slots/<sid>.qui-mod 를 쓴다, off 면 쓰지 않는다', { options: { site: 'prompt-hint' } }, async ($, on) => {
  for (const k of Object.keys(writes)) delete writes[k]
  stubEngine(on)
  await start($)
  // 시작 직후 남은 상태 읽기를 마치게 한다(마운트 없이 끝나면 테스트 종료 뒤 거부가 난다).
  await (await $.ui.mount({ ...MODE([]), surface: 'terminal' })).unmount()
  expect(Object.keys(writes)).toEqual(['/tmp/t/claude-subagent-slots/sid1.qui-mod'])
})

test('표지 파일: site=off 면 쓰지 않는다', { options: { site: 'off' } }, async ($, on) => {
  for (const k of Object.keys(writes)) delete writes[k]
  stubEngine(on)
  await start($)
  // 시작 직후 남은 상태 읽기를 마치게 한다(마운트 없이 끝나면 테스트 종료 뒤 거부가 난다).
  await (await $.ui.mount({ ...MODE([]), surface: 'terminal' })).unmount()
  expect(Object.keys(writes)).toEqual([])
})

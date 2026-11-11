import { expect, test } from 'claude-code/testing'

const MODE = (modes: string[]) =>
  ({ plugin: 'q-ui', component: 'SessionMode', requestId: 'mode', props: { modes } }) as const

const stubEngine = (on: any, extra: { style?: string } = {}) => {
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
  on('env.get', (_: any, e: any) => ({ value: e.name === 'HARNESS_STATUSLINE_STYLE' ? extra.style : '/home/x' }))
  on('fs.read', () => ({ deny: 'test: no file' }))
  on('clock.every', () => ({ value: null }))
}

test('SessionMode: 모드 + 묶음 한 줄 (plain)', async ($, on) => {
  stubEngine(on)
  await $.session.start({ cwd: '/work/claude-doctor', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...MODE(['auto']), surface: 'terminal' })
  const text = (await ui.findAll({ type: 'Text' })).map((t: any) => t.text).join('')
  expect(text).toBe('auto · claude-doctor:main* · Opus 5.5 ctx 30% · limit 5h 12% wk 31% reset 2h01m · $12.34')
  await ui.unmount()
})

test('SessionMode: nerd 스타일은 묶음마다 아이콘 하나', async ($, on) => {
  stubEngine(on, { style: 'nerd' })
  await $.session.start({ cwd: '/work/claude-doctor', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...MODE([]), surface: 'terminal' })
  const text = (await ui.findAll({ type: 'Text' })).map((t: any) => t.text).join('')
  expect(text).toContain(' claude-doctor:main*')
  expect(text).toContain(' Opus 5.5')
  expect(text).toContain(' 5h 12%')
  expect(text).toContain(' │ $12.34')
  await ui.unmount()
})

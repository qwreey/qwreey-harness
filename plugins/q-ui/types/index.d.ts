export type QuiSnap = {
  model: string
  effort: string
  ctxPct: number | null
  usd: number | null
  limits: { label: string; pct: number; resetsAt: string | null }[]
  branch: string
  dirty: boolean
}

declare module 'claude-code' {
  interface PluginState {
    'q-ui': { snap: QuiSnap | null }
  }
}

// PromptHint 의 hint 문자열(스크린 리더가 읽는 모양, 부분 사이 공백 하나)을 읽는다. 순수 함수: 엔진을 부르지 않는다.
// 모양은 실제 TUI 에서 확인한 것(사용자 시험: "auto mode on (shift+tab to cycle) · ← 1 agent")과 추정을 섞은 것이라,
// 모르는 모양이면 idle=false 로 돌려 엔진 힌트를 그대로 살린다(보수적).

export type HintInfo = {
  /** "auto", "plan", "accept edits" 처럼 짧은 모드 표지. 없으면 '' */
  mode: string
  /** "← N agent(s)" 알약의 N. 없으면 0 */
  agents: number
  /** 중요한 안내(esc to interrupt, 권한 대기 문구 등)가 아니고 모드·알약·"? for shortcuts" 만 있다 */
  idle: boolean
}

const MODE_RE = /([A-Za-z][A-Za-z ]*?)\s+on\s*\(shift\+tab to cycle\)/i
const AGENT_RE = /(?:←\s*)?(\d+)\s+(?:local\s+|background\s+)?agents?\b/i

export function parseHint(hint: string): HintInfo {
  let text = hint.replace(/\s+/g, ' ').trim()
  let mode = ''
  let agents = 0
  const m = MODE_RE.exec(text)
  if (m) {
    mode = (m[1] ?? '').replace(/\s+mode$/i, '').trim().toLowerCase()
    text = text.replace(m[0], ' ')
  }
  const a = AGENT_RE.exec(text)
  if (a) {
    agents = Number(a[1])
    text = text.replace(a[0], ' ')
  }
  // 구분 기호, 화살표, 모드 글리프, 남은 "↓ to view" 같은 알약 안내를 걷어낸 뒤 남는 것이 중요한 안내다.
  const rest = text
    .replace(/\? for shortcuts/gi, ' ')
    .replace(/[·•⏵←→↓↑|]+/g, ' ')
    .replace(/\b(?:to (?:view|manage|show|expand)|ctrl\+\w|shift\+tab to cycle)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return { mode, agents, idle: rest === '' }
}

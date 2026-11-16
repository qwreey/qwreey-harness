// The desk's contract: what it keeps for the session ($.state) and, per
// project directory, across sessions ($.store, under `project:<cwd>`).

export type DeskOption = { key: string; label: string; why?: string }

export type DeskDecisionStatus = 'open' | 'answered' | 'deferred'

/**
 * How much waits on a decision: `blocking` stops the work, `soon` the next
 * steps depend on it, `later` can wait. A decision without one is `soon`.
 */
export type DeskUrgency = 'blocking' | 'soon' | 'later'

export type DeskCommentBy = 'user' | 'agent'

/** One entry of a decision's thread, oldest first. */
export type DeskComment = {
  /** c1, c2, ... within the decision. */
  id: string
  by: DeskCommentBy
  text: string
  at: number
  /** The model has it: a person's comment sent from the outbox or in chat, every agent comment. */
  sent?: true
}

export type DeskDecision = {
  /** D1, D2, ... counted per project. */
  id: string
  /** One line. */
  question: string
  /** Markdown; shown in the detail view only. */
  context?: string
  options: DeskOption[]
  recommended?: string
  recommendedWhy?: string
  /** Absent on decisions stored before urgency was kept: read as `soon`. */
  urgency?: DeskUrgency
  /** What waits on it, one line; shown in the detail view. */
  blocks?: string
  status: DeskDecisionStatus
  /** The person's own words. */
  answer?: string
  /** The thread under the decision: the person's comments and the agent's replies. */
  comments?: DeskComment[]
  /** The person's next comment as typed so far in the desk's box. */
  draft?: string
  /** When the draft was last saved. */
  draftAt?: number
  /** An agent comment the person has not opened the decision to read. */
  unread?: true
  /**
   * The single note of the older layout, read once into the thread as its
   * first comment (`migrate`); never written.
   */
  memo?: string
  memoAt?: number
  memoPending?: true
  /** The option the person picked on the desk, waiting in the outbox. */
  pick?: string
  createdAt: number
  answeredAt?: number
}

export type DeskStepState = 'todo' | 'doing' | 'done'

export type DeskStep = {
  id: string
  /** A short title; the timeline wraps it to a few lines. */
  text: string
  state: DeskStepState
  /** A line or two under the title; whole in the step's detail view. */
  detail?: string
  /** When it was first marked doing. */
  startedAt?: number
  /** When it was marked done. */
  endedAt?: number
}

export type DeskRunStatus = 'running' | 'done' | 'failed' | 'stopped' | 'lost'

export type DeskRun = {
  /** An agent's id, or a background shell's task id. */
  id: string
  kind: 'agent' | 'shell'
  label: string
  model?: string
  startedAt: number
  endedAt?: number
  status: DeskRunStatus
}

export type DeskLogKind = 'done' | 'agent' | 'decision' | 'note'

/** One entry of the work log: a model's note (a summary of finished work) or what the desk logged itself. */
export type DeskLogEntry = { at: number; kind: DeskLogKind; text: string }

export type DeskData = {
  decisions: DeskDecision[]
  plan: DeskStep[]
  running: DeskRun[]
  log: DeskLogEntry[]
  /** When the person last opened the 기록 tab; log entries after it are unseen. */
  lastSeen: number
  nextDecision: number
  /** The outbox's remark over all its decisions, sent with them. */
  outboxNote?: string
}

/** What `$.store` keeps under `project:<cwd>`. */
export type DeskStored = { shape: string; value: DeskData }

/** Which part of the pane shows: the tabs, a decision's or a step's detail, or the outbox. */
export type DeskView = {
  decision?: string
  step?: string
  outbox?: true
  /** The first piece of the detail's body shown: 0 at its top, absent where it opens. */
  offset?: number
}

/**
 * A desk field's session mark, by field (`memo-D3`, `outbox-note`). A
 * terminal field holds its own text once typed in, empties it when its Enter
 * settles, and shows the hook's `value` again only when that value changes or
 * the key does; so each Enter moves `rev`, which the field's key carries.
 * `submitted` lasts from an Enter to the next change the desk keeps.
 */
export type DeskField = { rev: number; submitted?: true }

/** The pane's tabs: decisions waiting, the plan as a timeline, the work log (`away`, drawn as 기록). */
export type DeskTab = 'wait' | 'tasks' | 'away'

declare module 'claude-code' {
  interface PluginState {
    'qwreey-desk': {
      data: Shaped<DeskData>
      /** The store key this session reads and writes (`project:<cwd>`). */
      storeKey: string
      /** `lastSeen` as it stood when the 기록 tab was last opened: where its 여기부터 새로 rule stands. */
      seenFrom: number
      view: DeskView
      tab: DeskTab
      fields: Record<string, DeskField>
      /** Per tab: the first item its list shows, -1 where it opens on its own. */
      offset: StateFamily<number>
    }
  }
}

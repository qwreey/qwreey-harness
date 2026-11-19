// The desk's contract: what it keeps for the session ($.state), per project
// directory across sessions ($.store, under `project:<cwd>`), and what it
// reads back from the record files it writes under the project's `.claude/`.

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

/**
 * What a decision's file holds that the desk does not know, written back as
 * it was read: frontmatter lines of other keys, text between the title and
 * the first section, sections of other names.
 */
export type DeskKept = { head?: string[]; lead?: string; sections?: string[] }

export type DeskDecision = {
  /** Q1, Q2, ... counted per project (D<n> before files: the same number). */
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
  /** Its file, relative to the project folder, once written or read there. */
  file?: string
  /** What its file holds beyond the desk's own fields. */
  kept?: DeskKept
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

/** What only the desk keeps of a decision: the person's unsent picks and comments, read marks. */
export type DeskMarks = {
  pick?: string
  draft?: string
  draftAt?: number
  unread?: true
  /** The person's comments waiting in the outbox; a comment joins the file once sent. */
  unsent?: DeskComment[]
}

/** When a step started and ended, kept for the step of that id while its title stays. */
export type DeskTimes = { text: string; startedAt?: number; endedAt?: number }

/**
 * What `$.store` keeps under `project:<cwd>` (tag `desk-2`): the pane's own
 * state. Decisions and the plan are files under the project's `.claude/`;
 * where it has no folder the desk can write, they stay here
 * (`decisions`, `plan`).
 */
export type DeskUi = {
  running: DeskRun[]
  log: DeskLogEntry[]
  lastSeen: number
  nextDecision: number
  outboxNote?: string
  /** By decision id. */
  marks: Record<string, DeskMarks>
  /** By step id. */
  times: Record<string, DeskTimes>
  decisions?: DeskDecision[]
  plan?: DeskStep[]
}

export type DeskStored = { shape: string; value: DeskUi }

/** The store's value under the older tag `desk-1`: the whole desk; read once into files and `desk-2`. */
export type DeskStoredV1 = { shape: string; value: DeskData }

/** Where the session's desk lives: the store key, and the project folder its files go under. */
export type DeskBacking = {
  /** `project:<cwd>`; '' until the desk has been read in this process. */
  storeKey: string
  /** The project folder; absent when everything stays in the store. */
  root?: string
  /** Why there are no files, shown once in the band. */
  reason?: string
  /** The band has shown `reason` and the person has sent a prompt since. */
  told?: true
}

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
      backing: DeskBacking
      /** `lastSeen` as it stood when the 기록 tab was last opened: where its 여기부터 새로 rule stands. */
      seenFrom: number
      view: DeskView
      tab: DeskTab
      fields: Record<string, DeskField>
      /** Per tab: the first item its list shows, -1 where it opens on its own. */
      offset: StateFamily<number>
      /** The last "no step doing" reminder: the plan it was for, and prompts since. */
      idleNudge: { sig: string; prompts: number }
    }
  }
}

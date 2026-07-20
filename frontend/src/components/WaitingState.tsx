import type { ReactNode } from 'react'

import { UiIcon } from './UiIcon'

export type WaitingPhase = 'requesting' | 'cooldown'

type WaitingStateProps = {
  readonly children: ReactNode
  readonly iconClassName?: string
  readonly phase: WaitingPhase
}

export function WaitingState({ children, iconClassName, phase }: WaitingStateProps): JSX.Element {
  const iconClass = ['waiting-state-icon', iconClassName].filter(Boolean).join(' ')
  return (
    <span className="waiting-state" data-waiting-phase={phase}>
      <span className="waiting-state-visual">
        <UiIcon className={iconClass} name="refresh" />
        <span aria-hidden="true" className="waiting-state-marker" data-waiting-marker="true" />
      </span>
      {children}
    </span>
  )
}

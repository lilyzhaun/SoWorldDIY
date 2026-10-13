import { UiIcon, type UiIconName } from './UiIcon'

export type StatusTone = 'info' | 'success' | 'warning' | 'error'

type StatusMessageProps = {
  readonly className?: string
  readonly message: string
  readonly tone: StatusTone
}

type StatusPresentation = {
  readonly icon: UiIconName
  readonly live?: 'polite'
  readonly role: 'alert' | 'status'
}

const STATUS_PRESENTATIONS = {
  info: { icon: 'info-circle', live: 'polite', role: 'status' },
  success: { icon: 'check-circle', live: 'polite', role: 'status' },
  warning: { icon: 'alert-triangle', role: 'alert' },
  error: { icon: 'x-circle', role: 'alert' },
} as const satisfies Record<StatusTone, StatusPresentation>

export function StatusMessage({ className, message, tone }: StatusMessageProps): React.JSX.Element {
  const presentation: StatusPresentation = STATUS_PRESENTATIONS[tone]
  const rootClassName = `status-message status-message--${tone}${className ? ` ${className}` : ''}`

  return (
    <div className={rootClassName} role={presentation.role} aria-live={presentation.live} aria-atomic="true">
      <UiIcon name={presentation.icon} size={18} />
      <span>{message}</span>
    </div>
  )
}

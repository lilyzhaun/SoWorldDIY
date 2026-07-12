export type UiIconName =
  | 'alert-triangle'
  | 'arrow-left'
  | 'calendar'
  | 'check'
  | 'check-circle'
  | 'chevron-down'
  | 'chevron-right'
  | 'circle'
  | 'close'
  | 'info-circle'
  | 'minus'
  | 'phone'
  | 'plus'
  | 'refresh'
  | 'search'
  | 'trash'
  | 'user'
  | 'x-circle'

type UiIconProps = {
  readonly className?: string
  readonly name: UiIconName
  readonly size?: 16 | 18 | 20
}

function renderIcon(name: UiIconName): JSX.Element {
  switch (name) {
    case 'alert-triangle':
      return <><path d="M10 2.5 18 17H2L10 2.5Z" /><path d="M10 7.25v4.5" /><path d="M10 14.5h.01" /></>
    case 'arrow-left':
      return <><path d="m8 4-6 6 6 6" /><path d="M2 10h16" /></>
    case 'calendar':
      return <><rect x="2.5" y="4" width="15" height="13.5" rx="2" /><path d="M6 2v4M14 2v4M2.5 8h15" /></>
    case 'check':
      return <path d="m3.5 10.25 4 4 9-9" />
    case 'check-circle':
      return <><circle cx="10" cy="10" r="7.5" /><path d="m6.5 10 2.25 2.25L13.75 7" /></>
    case 'chevron-down':
      return <path d="m4.5 7.5 5.5 5 5.5-5" />
    case 'chevron-right':
      return <path d="m7.5 4.5 5 5.5-5 5.5" />
    case 'circle':
      return <circle cx="10" cy="10" r="3.25" fill="currentColor" stroke="none" />
    case 'close':
      return <path d="m4.5 4.5 11 11m0-11-11 11" />
    case 'info-circle':
      return <><circle cx="10" cy="10" r="7.5" /><path d="M10 9v5M10 6h.01" /></>
    case 'minus':
      return <path d="M4 10h12" />
    case 'phone':
      return <path d="M6.25 2.75 8.5 7 6.75 8.5a12.6 12.6 0 0 0 4.75 4.75L13 11.5l4.25 2.25-.75 3.5c-.15.65-.75 1.1-1.4 1A15.2 15.2 0 0 1 1.75 4.9c-.1-.65.35-1.25 1-1.4l3.5-.75Z" />
    case 'plus':
      return <path d="M10 4v12M4 10h12" />
    case 'refresh':
      return <><path d="M16.5 7A7 7 0 1 0 17 12" /><path d="M16.5 3v4h-4" /></>
    case 'search':
      return <><circle cx="8.75" cy="8.75" r="5.75" /><path d="m13 13 4 4" /></>
    case 'trash':
      return <><path d="M3.5 5.5h13M8 2.5h4l1 3H7l1-3ZM5.5 5.5l.75 12h7.5l.75-12" /><path d="M8.5 9v5M11.5 9v5" /></>
    case 'user':
      return <><circle cx="10" cy="6.5" r="3.25" /><path d="M3.5 17c.75-3.25 3-5 6.5-5s5.75 1.75 6.5 5" /></>
    case 'x-circle':
      return <><circle cx="10" cy="10" r="7.5" /><path d="m7.25 7.25 5.5 5.5m0-5.5-5.5 5.5" /></>
    default: {
      const exhaustiveName: never = name
      return exhaustiveName
    }
  }
}

export function UiIcon({ className, name, size = 20 }: UiIconProps): JSX.Element {
  return (
    <svg
      aria-hidden="true"
      className={className}
      data-ui-icon={name}
      fill="none"
      focusable="false"
      height={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.9"
      viewBox="0 0 20 20"
      width={size}
    >
      {renderIcon(name)}
    </svg>
  )
}

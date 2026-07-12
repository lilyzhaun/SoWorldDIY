import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { StatusMessage, type StatusTone } from './StatusMessage'

vi.mock('./UiIcon', () => ({
  UiIcon: ({ name, size }: { readonly name: string; readonly size: number }) => (
    <svg data-icon={name} width={size} height={size} aria-hidden="true" />
  ),
}))

const toneCases = [
  { tone: 'info', icon: 'info-circle', role: 'status', live: 'polite' },
  { tone: 'success', icon: 'check-circle', role: 'status', live: 'polite' },
  { tone: 'warning', icon: 'alert-triangle', role: 'alert', live: null },
  { tone: 'error', icon: 'x-circle', role: 'alert', live: null },
] as const satisfies readonly {
  readonly tone: StatusTone
  readonly icon: string
  readonly role: 'alert' | 'status'
  readonly live: 'polite' | null
}[]

describe('StatusMessage', () => {
  it.each(toneCases)('renders the $tone tone with its semantic icon and announcement behavior', ({ tone, icon, role, live }) => {
    const html = renderToStaticMarkup(<StatusMessage message={`${tone} message`} tone={tone} />)

    expect(html).toContain(`class="status-message status-message--${tone}"`)
    expect(html).toContain(`role="${role}"`)
    expect(html).toContain('aria-atomic="true"')
    expect(html).toContain(`data-icon="${icon}"`)
    expect(html).toContain('width="18"')
    expect(html).toContain('height="18"')
    expect(html).toContain(`<span>${tone} message</span>`)
    if (live === null) {
      expect(html).not.toContain('aria-live=')
    } else {
      expect(html).toContain(`aria-live="${live}"`)
    }
  })

  it('preserves the exact message and appends an optional class without emoji', () => {
    const message = 'Account details updated.'
    const html = renderToStaticMarkup(<StatusMessage className="account-status" message={message} tone="success" />)

    expect(html).toContain('class="status-message status-message--success account-status"')
    expect(html).toContain(`<span>${message}</span>`)
    expect(html).not.toMatch(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]/u)
  })
})

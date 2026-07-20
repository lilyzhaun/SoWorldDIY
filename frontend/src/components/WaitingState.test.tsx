import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { WaitingState } from './WaitingState'

function renderWaitingState(overrides: Partial<Parameters<typeof WaitingState>[0]> = {}): string {
  return renderToStaticMarkup(
    <WaitingState phase="requesting" {...overrides}>
      正在获取号码…
    </WaitingState>,
  )
}

describe('WaitingState', () => {
  it('renders the shared refresh icon, a static marker, the phase attribute, and children', () => {
    const html = renderWaitingState()

    expect(html).toContain('class="waiting-state"')
    expect(html).toContain('data-waiting-phase="requesting"')
    expect(html).toContain('data-ui-icon="refresh"')
    expect(html).toContain('waiting-state-icon')
    expect(html).toContain('waiting-state-marker')
    expect(html).toContain('aria-hidden="true"')
    expect(html).toContain('正在获取号码…')
  })

  it('exposes the cooldown phase through data-waiting-phase', () => {
    const html = renderWaitingState({ phase: 'cooldown' })

    expect(html).toContain('data-waiting-phase="cooldown"')
    expect(html).not.toContain('data-waiting-phase="requesting"')
  })

  it('merges an optional icon class while keeping the waiting-state icon class', () => {
    const html = renderWaitingState({ iconClassName: 'refresh-btn-icon' })

    expect(html).toContain('waiting-state-icon refresh-btn-icon')
  })
})

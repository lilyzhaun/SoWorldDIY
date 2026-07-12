import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { CartQuantityModal } from './CartQuantityModal'

const DRAFT = { name: '本地数据', offerId: 'offer-1', price: 20, quantity: 2 } as const

function renderModal(phase: 'entered' | 'exiting'): string {
  return renderToStaticMarkup(
    <CartQuantityModal
      cart={[]}
      draft={DRAFT}
      onCancel={vi.fn()}
      onConfirm={vi.fn()}
      onExitComplete={vi.fn()}
      onUpdateDraft={vi.fn()}
      phase={phase}
    />,
  )
}

describe('CartQuantityModal presence', () => {
  it('shows the interactive overlay while entered', () => {
    const html = renderModal('entered')

    expect(html).toContain('class="modal-overlay show"')
    expect(html).toContain('id="cartQuantityModal"')
    expect(html).toContain('role="dialog"')
    expect(html).toContain('aria-modal="true"')
    expect(html).toContain('aria-labelledby="cartQuantityModalTitle"')
    expect(html).toContain('id="cartQuantityModalTitle"')
    expect(html).toContain('value="2"')
    expect(html).not.toContain('id="customModal"')
  })

  it('retains the draft while marking the overlay non-interactive during exit', () => {
    const html = renderModal('exiting')

    expect(html).toContain('class="modal-overlay is-exiting"')
    expect(html).toContain('data-dialog-accessibility-active="true"')
    expect(html).toContain('本地数据')
    expect(html).toContain('value="2"')
  })
})

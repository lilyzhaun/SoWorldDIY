import { cleanup, fireEvent, render } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ActiveOffer } from '@/types'
import { ActiveOffersSection } from './ActiveOffersSection'

afterEach(cleanup)

function bonus(instanceId?: string): ActiveOffer {
  return {
    offerId: 'bonus-300',
    instanceId,
    name: '增值獎賞 (300本地通話分鐘)',
    planStatus: 'ACTIVE',
    endDate: '2027-10-21',
    usage: [{ name: 'Local Voice 300 Minutes', unit: 'Minutes', total: 300, remain: 300, percent: 100 }],
  }
}

function OfferList({ offers }: { readonly offers: ActiveOffer[] }): React.JSX.Element {
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  return (
    <ActiveOffersSection
      currentSub={{ subscriptionId: 'sub-1', activeOffers: offers }}
      onOpenTransfer={vi.fn()}
      onRefresh={vi.fn()}
      onSelectOffer={setSelectedPlanId}
      refreshingUsage={false}
      selectedPlanId={selectedPlanId}
      visible
    />
  )
}

describe('active offer instances', () => {
  it.each([true, false])('expands repeated bonuses independently (instance IDs: %s)', (hasInstanceIds) => {
    const offers = hasInstanceIds
      ? [bonus('bonus-300-resource-38'), bonus('bonus-300-resource-33')]
      : [bonus(), bonus()]
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      const view = render(<OfferList offers={offers} />)
      const cards = view.getAllByRole('button', { name: /增值獎賞/ })
      expect(cards).toHaveLength(2)
      expect(view.getAllByText('剩 300分钟 / 总 300分钟')).toHaveLength(2)
      const detailIds = cards.map((card) => card.getAttribute('aria-controls'))
      expect(new Set(detailIds).size).toBe(2)
      for (const id of detailIds) expect(document.getElementById(id!)).not.toBeNull()

      fireEvent.click(cards[0])
      expect(cards.map((card) => card.getAttribute('aria-expanded'))).toEqual(['true', 'false'])
      fireEvent.click(cards[1])
      expect(cards.map((card) => card.getAttribute('aria-expanded'))).toEqual(['false', 'true'])
      fireEvent.click(cards[1])
      expect(cards.map((card) => card.getAttribute('aria-expanded'))).toEqual(['false', 'false'])
      expect(consoleError).not.toHaveBeenCalled()
    } finally {
      consoleError.mockRestore()
    }
  })

  it('keeps the selected instance open when a refresh reorders repeated offers', () => {
    const offers = [bonus('bonus-300-resource-38'), bonus('bonus-300-resource-33')]
    const view = render(<OfferList offers={offers} />)
    const first = view.getAllByRole('button', { name: /增值獎賞/ })[0]
    const selectedDetails = first.getAttribute('aria-controls')
    fireEvent.click(first)

    view.rerender(<OfferList offers={[...offers].reverse()} />)

    const cards = view.getAllByRole('button', { name: /增值獎賞/ })
    expect(cards.map((card) => card.getAttribute('aria-expanded'))).toEqual(['false', 'true'])
    expect(cards[1].getAttribute('aria-controls')).toBe(selectedDetails)
  })

  it('uses the catalog offer ID rather than the instance ID for transfers', () => {
    const onOpenTransfer = vi.fn()
    const offer = bonus('bonus-300-resource-38')
    offer.usage![0] = { ...offer.usage![0], canTransfer: true, balanceResourceId: 'balance-33' }
    const view = render(
      <ActiveOffersSection
        currentSub={{ subscriptionId: 'sub-1', activeOffers: [offer] }}
        onOpenTransfer={onOpenTransfer}
        onRefresh={vi.fn()}
        onSelectOffer={vi.fn()}
        refreshingUsage={false}
        selectedPlanId="sub-bonus-300-resource-38"
        visible
      />,
    )

    fireEvent.click(view.getByRole('button', { name: '转移' }))

    expect(onOpenTransfer).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ userOfferId: 'bonus-300', balanceResourceId: 'balance-33' }),
    )
  })
})

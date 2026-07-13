import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { parseCmnPattern } from '@/utils/cmnPattern'
import { ActiveOffersSection } from './ActiveOffersSection'
import { CmnSection } from './CmnSection'
import { MainHeader } from './MainHeader'
import { PlanList } from './PlanList'

describe('navigation presentation contracts', () => {
  it('renders semantic SVG icons without legacy character controls', () => {
    const currentSub = {
      subscriptionId: 'sub-1',
      mobile: '51234567',
      activeOffers: [{ offerId: 'offer-1', name: '测试套餐', endDate: '2026-12-31' }],
    }
    const activeOffers = renderToStaticMarkup(
      <ActiveOffersSection
        currentSub={currentSub}
        onOpenTransfer={vi.fn()}
        onRefresh={vi.fn()}
        onSelectOffer={vi.fn()}
        refreshingUsage={false}
        selectedPlanId="sub-offer-1"
        visible
      />,
    )
    const cmnInitial = renderToStaticMarkup(
      <CmnSection
        autoRefresh={{ kind: 'idle', message: '' }}
        canRefresh
        cooldown={0}
        data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }}
        error=""
        loading={false}
        numbers={[]}
        numbersLoading={false}
        onAutoRefreshCancel={vi.fn()}
        onAutoRefreshStart={vi.fn()}
        onPatternChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectNumber={vi.fn()}
        onSubmit={vi.fn()}
        parsedPattern={parseCmnPattern('')}
        pattern=""
        selectedNumber={null}
        visible
      />,
    )
    const cmnCooldown = renderToStaticMarkup(
      <CmnSection
        autoRefresh={{ kind: 'idle', message: '' }}
        canRefresh={false}
        cooldown={8}
        data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }}
        error=""
        loading={false}
        numbers={['66612345']}
        numbersLoading={false}
        onAutoRefreshCancel={vi.fn()}
        onAutoRefreshStart={vi.fn()}
        onPatternChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectNumber={vi.fn()}
        onSubmit={vi.fn()}
        parsedPattern={parseCmnPattern('')}
        pattern=""
        selectedNumber={null}
        visible
      />,
    )
    const plans = renderToStaticMarkup(
      <PlanList
        filteredPlans={[
          { offerId: 'offer-1', name: '测试套餐', price: 10, validity: '30日', desc: '说明', category: 'LOCAL' },
        ]}
        noNumberMode={false}
        onAddToCart={vi.fn()}
        onSelectPlan={vi.fn()}
        plansLoading={false}
        selectedPlanId="offer-1"
        showFreePlans={false}
        visible
      />,
    )
    const header = renderToStaticMarkup(
      <MainHeader
        availableAccounts={[{ identifier: 'account-1', active: true, subBrand: 'SoSIM' }]}
        balance="10"
        category="ALL"
        currentSub={currentSub}
        noNumberMode={false}
        onLogout={vi.fn()}
        onOpenHistory={vi.fn()}
        onOpenInbox={vi.fn()}
        onOpenSwitch={vi.fn()}
        onSearchChange={vi.fn()}
        onShowAlert={vi.fn()}
        onSwitchCategory={vi.fn()}
        search=""
      />,
    )
    const html = [activeOffers, cmnInitial, cmnCooldown, plans, header].join('')

    for (const legacyIcon of ['🔍', '🔄', '⏳', '⚠️', '↻', '▼', '📅']) {
      expect(html).not.toContain(legacyIcon)
    }
    expect(cmnInitial).toContain('<svg')
    expect(cmnCooldown).toContain('<svg')
    expect(cmnCooldown).toContain('（8s）')
    expect(activeOffers).toContain('class="plan-card open"')
    expect(activeOffers).toContain(
      '<button type="button" class="plan-card-disclosure" aria-expanded="true" aria-controls="active-offer-details-offer-1"',
    )
    expect(activeOffers).not.toContain('<div class="plan-card open" role="button"')
    expect(activeOffers).toContain('id="active-offer-details-offer-1" class="card-details open" aria-hidden="false"')
    expect(plans).toContain('class="plan-card open"')
    expect(plans).toContain(
      '<button type="button" class="plan-card-disclosure" aria-expanded="true" aria-controls="plan-details-offer-1"',
    )
    expect(plans).not.toContain('<div class="plan-card open" role="button"')
    expect(plans).toContain('id="plan-details-offer-1" class="card-details open" aria-hidden="false"')
    expect(header).toContain('id="u_switch_hint"')
    expect(header).toContain('<button type="button" id="u_switch_hint"')
    expect(header).toContain('<button type="button" class="cat-tab active"')
    expect(header).not.toContain('role="button"')
    expect(header).not.toContain('tabindex="0"')
  })

  it('removes collapsed disclosure controls from the tab order without unmounting animated details', () => {
    const plans = renderToStaticMarkup(
      <PlanList
        filteredPlans={[
          { offerId: 'offer-1', name: '测试套餐', price: 10, validity: '30日', desc: '说明', category: 'LOCAL' },
        ]}
        noNumberMode={false}
        onAddToCart={vi.fn()}
        onSelectPlan={vi.fn()}
        plansLoading={false}
        selectedPlanId={null}
        showFreePlans={false}
        visible
      />,
    )
    const currentSub = {
      subscriptionId: 'sub-1',
      mobile: '51234567',
      activeOffers: [
        {
          offerId: 'offer-1',
          name: '测试套餐',
          endDate: '2026-12-31',
          usage: [
            {
              name: '数据',
              canTransfer: true,
              balanceResourceId: 'resource-1',
              unit: 'megabytes',
              minTransfer: 10,
              productFamily: 'data',
              remain: 100,
            },
          ],
        },
      ],
    }
    const activeOffers = renderToStaticMarkup(
      <ActiveOffersSection
        currentSub={currentSub}
        onOpenTransfer={vi.fn()}
        onRefresh={vi.fn()}
        onSelectOffer={vi.fn()}
        refreshingUsage={false}
        selectedPlanId={null}
        visible
      />,
    )

    expect(plans).toContain('id="plan-details-offer-1" class="card-details " aria-hidden="true" inert=""')
    expect(plans).toContain('加入购物车')
    expect(activeOffers).toContain(
      'id="active-offer-details-offer-1" class="card-details " aria-hidden="true" inert=""',
    )
    expect(activeOffers).toContain('>转移</button>')
  })
})

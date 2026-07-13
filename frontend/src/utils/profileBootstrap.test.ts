import { describe, expect, it } from 'vitest'

import type { Plan, Subscription } from '@/types'
import { selectProfileSubscription, sortPlansByPrice } from '@/utils/profileBootstrap'

const subscriptions: readonly Subscription[] = [{ subscriptionId: 'first' }, { subscriptionId: 'selected' }]

describe('selectProfileSubscription', () => {
  it('uses the current subscription ID when it matches an available subscription', () => {
    const backendCurrent: Subscription = { subscriptionId: 'backend' }

    const selection = selectProfileSubscription(subscriptions, backendCurrent, 'selected')

    expect(selection).toEqual({ currentSubId: 'selected', noNumberMode: false })
  })

  it('falls back to the backend current subscription when the current ID is unavailable', () => {
    const backendCurrent: Subscription = { subscriptionId: 'backend' }

    const selection = selectProfileSubscription(subscriptions, backendCurrent, 'missing')

    expect(selection).toEqual({ currentSubId: 'backend', noNumberMode: false })
  })

  it('falls back to the first subscription when neither preferred subscription is available', () => {
    const selection = selectProfileSubscription(subscriptions, undefined, 'missing')

    expect(selection).toEqual({ currentSubId: 'first', noNumberMode: false })
  })

  it('enables no-number mode when no subscription is available', () => {
    const selection = selectProfileSubscription([], undefined, '')

    expect(selection).toEqual({ currentSubId: '', noNumberMode: true })
  })
})

describe('sortPlansByPrice', () => {
  it('returns plans in ascending price order without mutating the input', () => {
    const expensive: Plan = {
      offerId: 'expensive',
      name: 'Expensive',
      price: 30,
      validity: '',
      desc: '',
      category: 'OTHER',
    }
    const cheap: Plan = { offerId: 'cheap', name: 'Cheap', price: 10, validity: '', desc: '', category: 'OTHER' }
    const plans = [expensive, cheap]

    const sorted = sortPlansByPrice(plans)

    expect(sorted).toEqual([cheap, expensive])
    expect(sorted).not.toBe(plans)
    expect(plans).toEqual([expensive, cheap])
  })
})

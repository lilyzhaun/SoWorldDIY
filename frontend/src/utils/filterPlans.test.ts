import { describe, expect, it } from 'vitest'

import type { Category, Plan } from '@/types'

import { filterPlansForCategory } from './filterPlans'

const plans: Plan[] = [
  { offerId: '1', name: 'Local A', price: 10, validity: '1d', desc: 'local data', category: 'LOCAL' },
  { offerId: '2', name: 'Travel B', price: 20, validity: '7d', desc: 'roam', category: 'TRAVEL' },
  { offerId: '3', name: 'Voice C', price: 0, validity: '1d', desc: 'free voice', category: 'VOICE' },
  { offerId: '4', name: 'Other D', price: 5, validity: '1d', desc: 'misc', category: 'OTHER' },
]

describe('filterPlansForCategory', () => {
  it('hides CMN and SUBSCRIBED categories entirely', () => {
    expect(filterPlansForCategory(plans, '', 'CMN' as Category, true)).toEqual([])
    expect(filterPlansForCategory(plans, '', 'SUBSCRIBED' as Category, true)).toEqual([])
  })

  it('filters free plans unless showFreePlans is true', () => {
    const paidOnly = filterPlansForCategory(plans, '', 'ALL', false)
    expect(paidOnly.every((p) => p.price > 0)).toBe(true)
    const withFree = filterPlansForCategory(plans, '', 'ALL', true)
    expect(withFree.some((p) => p.price <= 0)).toBe(true)
  })

  it('filters by category including OTHER mapping', () => {
    const local = filterPlansForCategory(plans, '', 'LOCAL', true)
    expect(local.map((p) => p.offerId)).toEqual(['1'])
    const other = filterPlansForCategory(plans, '', 'OTHER', true)
    expect(other.map((p) => p.offerId).sort()).toEqual(['3', '4'])
  })

  it('applies keyword search across name, desc, and price', () => {
    expect(filterPlansForCategory(plans, 'roam', 'ALL', true).map((p) => p.offerId)).toEqual(['2'])
    expect(filterPlansForCategory(plans, '20', 'ALL', true).map((p) => p.offerId)).toEqual(['2'])
    expect(filterPlansForCategory(plans, 'nomatch', 'ALL', true)).toEqual([])
  })
})

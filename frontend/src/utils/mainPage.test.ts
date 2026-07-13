import { describe, expect, it } from 'vitest'

import { formatStatus, getAccountIdFromPathname, getApiUrl, getIsoTime, normalizeUnit, stripHtml } from './mainPage'

describe('MainPage utilities', () => {
  it('extracts only the segment following main', () => {
    expect(getAccountIdFromPathname('/main/account-42/details')).toBe('account-42')
    expect(getAccountIdFromPathname('/login')).toBe('')
    expect(getAccountIdFromPathname('/main')).toBe('')
  })

  it('appends account identifiers without changing existing query ordering', () => {
    expect(getApiUrl('api/profile', '')).toBe('/api/profile')
    expect(getApiUrl('/api/profile', 'account-42')).toBe('/api/profile?account_id=account-42')
    expect(getApiUrl('/api/profile?refresh=true&_t=7', 'account-42')).toBe(
      '/api/profile?refresh=true&_t=7&account_id=account-42',
    )
  })

  it('strips markup while preserving text content', () => {
    expect(stripHtml('<strong>套餐</strong><script>alert(1)</script>')).toBe('套餐alert(1)')
    expect(stripHtml('plain text')).toBe('plain text')
  })

  it('returns exact status labels and colors', () => {
    expect(formatStatus('ACTIVE')).toEqual({ text: '正常', color: '#10b981' })
    expect(formatStatus('PREACTIVE')).toEqual({ text: '待激活', color: '#f59e0b' })
    expect(formatStatus('SUSPENDED')).toEqual({ text: '已停用', color: '#ef4444' })
    expect(formatStatus('TERMINATED')).toEqual({ text: '已停用', color: '#ef4444' })
    expect(formatStatus('UNKNOWN')).toEqual({ text: 'UNKNOWN', color: '#718096' })
    expect(formatStatus()).toEqual({ text: '--', color: '#718096' })
  })

  it('normalizes known units and preserves unknown units', () => {
    expect(normalizeUnit('Megabytes')).toBe('MB')
    expect(normalizeUnit('minutes')).toBe('分钟')
    expect(normalizeUnit('DAYS')).toBe('天')
    expect(normalizeUnit('SMS')).toBe('SMS')
    expect(normalizeUnit()).toBe('')
  })

  it('formats local date boundaries exactly', () => {
    const date = new Date(2026, 6, 11, 12, 30)

    expect(getIsoTime(date)).toBe('2026-07-11T00:00:00.000')
    expect(getIsoTime(date, true)).toBe('2026-07-11T23:59:59.999')
  })
})

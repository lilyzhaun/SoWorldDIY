import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { parseCmnPattern } from '@/utils/cmnPattern'
import { CmnSection } from './CmnSection'

describe('CMN presentation contracts', () => {
  it('renders at most nine CMN candidates for a three-by-three grid', () => {
    const numbers = Array.from({ length: 10 }, (_, index) => String(60000000 + index))
    const html = renderToStaticMarkup(
      <CmnSection
        autoRefresh={{ kind: 'idle', message: '' }}
        canRefresh
        cooldown={0}
        data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }}
        error=""
        loading={false}
        numbers={numbers}
        numbersLoading={false}
        onAutoRefreshCancel={vi.fn()}
        onAutoRefreshStart={vi.fn()}
        onPatternChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectNumber={vi.fn()}
        onSubmit={vi.fn()}
        parsedPattern={parseCmnPattern('6[0-9]{2}')}
        pattern="6[0-9]{2}"
        selectedNumber={null}
        visible
      />,
    )

    expect((html.match(/class="num-btn /g) || []).length).toBe(9)
    expect(html).not.toContain(numbers[9])
  })

  it('renders accessible safe-pattern search, auto-refresh guidance, and React mark nodes', () => {
    const numbers = [
      '66612345',
      '12345666',
      '88888888',
      '10000000',
      '20000000',
      '30000000',
      '40000000',
      '50000000',
      '60000000',
    ]
    const html = renderToStaticMarkup(
      <CmnSection
        autoRefresh={{ kind: 'idle', message: '' }}
        canRefresh
        cooldown={0}
        data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }}
        error=""
        loading={false}
        numbers={numbers}
        numbersLoading={false}
        onAutoRefreshCancel={vi.fn()}
        onAutoRefreshStart={vi.fn()}
        onPatternChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectNumber={vi.fn()}
        onSubmit={vi.fn()}
        parsedPattern={parseCmnPattern('666')}
        pattern="666"
        selectedNumber="66612345"
        visible
      />,
    )

    expect(html).toContain('id="cmn-pattern-input" class="cmn-pattern-input"')
    expect(html).toContain('maxLength="32"')
    expect(html).toContain('autoComplete="off"')
    expect(html).toContain('aria-describedby="cmn-pattern-description cmn-auto-refresh-hint cmn-auto-refresh-status"')
    expect(html).toContain('aria-invalid="false"')
    expect(html).toContain('class="num-btn selected"')
    expect(html).toContain('aria-pressed="true"')
    expect(html).toContain('aria-pressed="false"')
    expect(html).toContain('class="num-btn "')
    expect(html).toContain('<span class="num-btn-label"><mark class="cmn-match">666</mark><span>12345</span></span>')
    expect(html).toContain('<span class="num-btn-label"><span>12345</span><mark class="cmn-match">666</mark></span>')
    expect((html.match(/class="num-btn /g) || []).length).toBe(9)
    expect(html).toContain('长按可自动查找，最多 20 次')
    expect(html).not.toContain('onmousedown')
    expect(html).not.toContain('ontouchstart')
  })

  it('escapes invalid HTML-like input, reports an alert, and renders no highlights', () => {
    const pattern = '<img src=x onerror=alert(1)>'
    const html = renderToStaticMarkup(
      <CmnSection
        autoRefresh={{ kind: 'idle', message: '' }}
        canRefresh
        cooldown={0}
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
        parsedPattern={parseCmnPattern(pattern)}
        pattern={pattern}
        selectedNumber={null}
        visible
      />,
    )

    expect(html).toContain('role="alert"')
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;')
    expect(html).not.toContain('<img')
    expect(html).not.toContain('class="cmn-match"')
  })

  it('renders valid-pattern guidance and running cancel state with atomic status semantics', () => {
    const idle = renderToStaticMarkup(
      <CmnSection
        autoRefresh={{ kind: 'idle', message: '' }}
        canRefresh
        cooldown={0}
        data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }}
        error=""
        loading={false}
        numbers={['12345678']}
        numbersLoading={false}
        onAutoRefreshCancel={vi.fn()}
        onAutoRefreshStart={vi.fn()}
        onPatternChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectNumber={vi.fn()}
        onSubmit={vi.fn()}
        parsedPattern={parseCmnPattern('666')}
        pattern="666"
        selectedNumber={null}
        visible
      />,
    )
    const running = renderToStaticMarkup(
      <CmnSection
        autoRefresh={{ kind: 'running', attempt: 4, message: '正在自动查找第 4 批号码' }}
        canRefresh={false}
        cooldown={2}
        data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }}
        error=""
        loading={false}
        numbers={['12345678']}
        numbersLoading
        onAutoRefreshCancel={vi.fn()}
        onAutoRefreshStart={vi.fn()}
        onPatternChange={vi.fn()}
        onRefresh={vi.fn()}
        onSelectNumber={vi.fn()}
        onSubmit={vi.fn()}
        parsedPattern={parseCmnPattern('666')}
        pattern="666"
        selectedNumber={null}
        visible
      />,
    )

    expect(idle).toContain('长按可自动查找，最多 20 次')
    expect(idle).toContain('id="cmn-auto-refresh-start"')
    expect(idle).toContain('开始自动查找')
    expect(idle).toContain('aria-label="开始自动查找号码，最多 20 次"')
    expect(idle).toContain('type="button"')
    expect(idle).toContain('aria-describedby="cmn-pattern-description cmn-auto-refresh-hint cmn-auto-refresh-status"')
    expect(idle).not.toContain('aria-busy')
    expect(running).toContain('自动查找 4/20')
    expect(running).toContain('点击取消')
    expect(running).not.toContain('id="cmn-auto-refresh-start"')
    expect(running).toContain('aria-busy="true"')
    expect(running).not.toContain('disabled=""')
    expect(running).toContain(
      'id="cmn-auto-refresh-status" class="cmn-auto-refresh-status" role="status" aria-live="polite" aria-atomic="true"',
    )
  })
})

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

vi.mock('dompurify', () => ({
  default: { sanitize: (input: string): string => input },
}))

import { MainPage } from './MainPage'

function renderMainPage(pathname = '/main/account-42'): string {
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { location: { pathname } },
  })

  return renderToStaticMarkup(<MainPage />)
}

describe('MainPage rendered contract', () => {
  it('preserves the top-level structure and class names in order', () => {
    const html = renderMainPage()
    const orderedMarkers = [
      'id="current-account-id-ref"',
      'id="global-loader" class="global-loader entered"',
      'class="fixed-header-wrapper"',
      'class="mini-user-card"',
      'class="toolbar"',
      'class="category-tabs"',
      'class="content-wrapper"',
      'id="planList" class="plan-list"',
      'id="activeOffersContainer"',
      'id="cmnContainer"',
      'id="mainFooter" class="footer-note-main"',
      'id="cartFab" class="cart-fab"',
      'id="inboxModal" class="modal-overlay records-modal-overlay "',
      'id="historyModal" class="modal-overlay records-modal-overlay "',
      'id="customModal" class="modal-overlay  "',
    ]

    const markerIndexes = orderedMarkers.map((marker) => html.indexOf(marker))
    expect(markerIndexes.every((index) => index >= 0)).toBe(true)
    expect(markerIndexes).toEqual([...markerIndexes].sort((left, right) => left - right))
  })

  it('preserves exact initial visible text and category ordering', () => {
    const html = renderMainPage()

    expect(html).toContain('正在同步账户信息…')
    expect(html).toContain('<span id="u_mobile">加载中…</span>')
    expect(html).toContain('placeholder="搜索套餐..."')
    expect(html).toContain('正在加载套餐…')
    expect(html).not.toContain('正在加载套餐...')
    expect(html).toContain('仅供个人学习使用，高净值账号请勿使用本网站。')
    expect(html).toContain('如使用密码登录请于24h内更改密码。<br/>发生一切损失于本网站无关。')

    expect(html.match(/<button type="button" class="cat-tab/g)).toHaveLength(6)
    const categoryText = [...html.matchAll(/class="cat-tab(?: active)? ?"[^>]*>([^<]+)<\/button>/g)].map(
      (match) => match[1],
    )
    expect(categoryText).toEqual(['全部', '本地', '外遊', '已订购', '其他', '更换号码'])
  })

  it('marks the initial plan loading with the requesting waiting phase', () => {
    const html = renderMainPage()

    expect(html).toContain('正在加载套餐…')
    expect(html).toMatch(
      /<div class="loader"[^>]*><span class="waiting-state"[^>]*data-waiting-phase="requesting"[^>]*>/,
    )
    expect(html).toContain('role="status"')
    expect(html).toContain('aria-live="polite"')
    expect(html).toContain('aria-busy="true"')
    expect(html).toContain('waiting-state-marker')
  })

  it('preserves account-derived values, labels, and hidden initial states without footer links', () => {
    const html = renderMainPage('/main/account%20name')

    expect(html).toContain('id="current-account-id-ref" value="account%20name"')
    expect(html).toContain('aria-label="交易记录"')
    expect(html).toContain('aria-label="收件箱"')
    expect(html).toContain('aria-label="退出登录"')
    expect(html).not.toMatch(/<a(?:\s|>)/)
    expect(html).toContain('<button type="button" id="cartFab" class="cart-fab" style="display:none"')
    expect(html).toContain('id="activeOffersContainer" style="display:none"')
    expect(html).toContain('id="cmnContainer" style="display:none"')
  })
})

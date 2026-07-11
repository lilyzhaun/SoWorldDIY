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
      'id="global-loader" class="global-loader "',
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
      'id="inboxModal" class="modal-overlay "',
      'id="historyModal" class="modal-overlay "',
      'id="customModal" class="modal-overlay  "',
    ]

    const markerIndexes = orderedMarkers.map((marker) => html.indexOf(marker))
    expect(markerIndexes.every((index) => index >= 0)).toBe(true)
    expect(markerIndexes).toEqual([...markerIndexes].sort((left, right) => left - right))
  })

  it('preserves exact initial visible text and category ordering', () => {
    const html = renderMainPage()

    expect(html).toContain('正在同步账户信息...')
    expect(html).toContain('<span id="u_mobile">加载中...</span>')
    expect(html).toContain('placeholder="搜索套餐..."')
    expect(html).toContain('正在加载套餐...')
    expect(html).toContain('仅供个人学习使用，高净值账号请勿使用本网站。')
    expect(html).toContain('如使用密码登录请于24h内更改密码。<br/>发生一切损失于本网站无关。')

    const categoryText = [...html.matchAll(/class="cat-tab(?: active)? ?"[^>]*>([^<]+)<\/div>/g)].map((match) => match[1])
    expect(categoryText).toEqual(['全部', '本地', '外遊', '已订购', '其他', '更换号码'])
  })

  it('preserves account-derived values, links, labels, and hidden initial states', () => {
    const html = renderMainPage('/main/account%20name')

    expect(html).toContain('id="current-account-id-ref" value="account%20name"')
    expect(html).toContain('aria-label="交易记录"')
    expect(html).toContain('aria-label="收件箱"')
    expect(html).toContain('aria-label="退出登录"')
    expect(html).toContain('href="https://example.invalid/support"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
    expect(html).toContain('id="cartFab" class="cart-fab" style="display:none"')
    expect(html).toContain('id="activeOffersContainer" style="display:none"')
    expect(html).toContain('id="cmnContainer" style="display:none"')
  })
})

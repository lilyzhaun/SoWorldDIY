import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { AccountSwitchModalContent } from './AccountSwitchModalContent'
import { ActiveOffersSection } from './ActiveOffersSection'
import { CartFab } from './CartFab'
import { CartModalContent } from './CartModalContent'
import { CmnSection } from './CmnSection'
import { CustomModal } from './CustomModal'
import { MainFooter } from './MainFooter'
import { PurchaseModalContent } from './PurchaseModalContent'
import { TransferModalContent } from './TransferModalContent'
import { parseCmnPattern } from '../utils/cmnPattern'

describe('MainPage presentation component contracts', () => {
  it('preserves the section and floating-cart markup contracts', () => {
    const activeOffers = renderToStaticMarkup(<ActiveOffersSection currentSub={null} onOpenTransfer={vi.fn()} onRefresh={vi.fn()} onSelectOffer={vi.fn()} refreshingUsage={false} selectedPlanId={null} visible={false} />)
    const cmn = renderToStaticMarkup(<CmnSection canRefresh cooldown={0} data={null} error="" loading={false} numbers={[]} numbersLoading={false} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('')} pattern="" selectedNumber={null} visible={false} />)
    const footer = renderToStaticMarkup(<MainFooter visible />)
    const cartFab = renderToStaticMarkup(<CartFab count={2} onOpen={vi.fn()} total={12.3} />)

    expect(activeOffers).toContain('id="activeOffersContainer" style="display:none"')
    expect(activeOffers).toContain('id="activeOffersList" class="plan-list"')
    expect(activeOffers).toContain('id="activeEmptyState" class="empty-state"')
    expect(cmn).toContain('id="cmnContainer" style="display:none"')
    expect(cmn).toContain('更改电话号码服务')
    expect(footer).toContain('id="mainFooter" class="footer-note-main"')
    expect(footer).toContain('href="https://example.invalid/support"')
    expect(cartFab).toContain('id="cartFab" class="cart-fab" style="display:flex"')
    expect(cartFab).toContain('id="cartTotalPreview">$12.3</span>')
  })

  it('preserves purchase, cart, account-switch, and transfer body markup', () => {
    const purchase = renderToStaticMarkup(<PurchaseModalContent balance="20" draft={{ title: '测试商品', price: 30, txnAmount: 20, paymentType: 'ALCN', submitting: false, source: 'cart', newLine: false }} onChangeDraft={vi.fn()} showNewLineOption />)
    const cart = renderToStaticMarkup(<CartModalContent cart={[{ offerId: 'offer-1', name: '测试套餐', price: 5, quantity: 2 }]} onRemove={vi.fn()} onUpdateQuantity={vi.fn()} total={10} />)
    const account = renderToStaticMarkup(<AccountSwitchModalContent availableAccounts={[]} currentSubId="sub-1" onAddAccount={vi.fn()} onSwitchAccount={vi.fn()} onSwitchSubscription={vi.fn()} subscriptions={[]} />)
    const transfer = renderToStaticMarkup(<TransferModalContent amount="" draft={{ userOfferId: 'offer-1', balanceResourceId: 'resource-1', unit: 'megabytes', minTransfer: 10, productFamily: 'data', maxValue: 100 }} error="" onChangeAmount={vi.fn()} onChangeTarget={vi.fn()} target="" />)

    expect(purchase).toContain('id="modalPaySection" style="display:block"')
    expect(purchase).toContain('新开UFO')
    expect(cart).toContain('class="cart-item-title">测试套餐</div>')
    expect(cart).toContain('<span>总计</span><span style="color:#e53e3e">$10.0</span>')
    expect(account).toContain('添加账号')
    expect(transfer).toContain('资源转移 (MB)')
    expect(transfer).toContain('id="transErrorMsg" class="form-error-msg" style="display:none"')
  })

  it('preserves custom modal shell classes, handle placement, and actions order', () => {
    const html = renderToStaticMarkup(<CustomModal actions={<><button>取消</button><button>确认</button></>} mode="bottom-sheet" onClose={vi.fn()} open title="账号管理"><div>内容</div></CustomModal>)

    expect(html).toContain('id="customModal" class="modal-overlay show bottom-sheet-overlay"')
    expect(html.indexOf('class="modal-handle"')).toBeLessThan(html.indexOf('内容'))
    expect(html.indexOf('取消')).toBeLessThan(html.indexOf('确认'))
    expect(html).toContain('class="modal-actions" id="modalActions"')
  })

  it('renders at most nine CMN candidates for a three-by-three grid', () => {
    const numbers = Array.from({ length: 10 }, (_, index) => String(60000000 + index))
    const html = renderToStaticMarkup(<CmnSection canRefresh cooldown={0} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={numbers} numbersLoading={false} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('6[0-9]{2}')} pattern="6[0-9]{2}" selectedNumber={null} visible />)

    expect((html.match(/class="num-btn /g) || []).length).toBe(9)
    expect(html).not.toContain(numbers[9])
  })

  it('renders accessible safe-pattern search and React mark nodes without long-press behavior', () => {
    const numbers = ['66612345', '12345666', '88888888', '10000000', '20000000', '30000000', '40000000', '50000000', '60000000']
    const html = renderToStaticMarkup(<CmnSection canRefresh cooldown={0} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={numbers} numbersLoading={false} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('666')} pattern="666" selectedNumber="66612345" visible />)

    expect(html).toContain('id="cmn-pattern-input"')
    expect(html).toContain('maxLength="32"')
    expect(html).toContain('autoComplete="off"')
    expect(html).toContain('<mark>666</mark><span>12345</span>')
    expect(html).toContain('<span>12345</span><mark>666</mark>')
    expect((html.match(/class="num-btn /g) || []).length).toBe(9)
    expect(html).not.toContain('长按可手填')
    expect(html).not.toContain('onmousedown')
    expect(html).not.toContain('ontouchstart')
  })

  it('escapes invalid HTML-like input, reports an alert, and renders no highlights', () => {
    const pattern = '<img src=x onerror=alert(1)>'
    const html = renderToStaticMarkup(<CmnSection canRefresh cooldown={0} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={['66612345']} numbersLoading={false} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern(pattern)} pattern={pattern} selectedNumber={null} visible />)

    expect(html).toContain('role="alert"')
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;')
    expect(html).not.toContain('<img')
    expect(html).not.toContain('<mark>')
  })
})

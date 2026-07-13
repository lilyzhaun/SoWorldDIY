import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { parseCmnPattern } from '@/utils/cmnPattern'
import { AccountSwitchModalContent } from './AccountSwitchModalContent'
import { ActiveOffersSection } from './ActiveOffersSection'
import { CartFab } from './CartFab'
import { CartModalContent } from './CartModalContent'
import { CmnSection } from './CmnSection'
import { CustomModal } from './CustomModal'
import { MainFooter } from './MainFooter'
import { PurchaseModalContent } from './PurchaseModalContent'
import { TransferModalContent } from './TransferModalContent'

describe('presentation shell contracts', () => {
  it('preserves the section and floating-cart markup contracts', () => {
    const activeOffers = renderToStaticMarkup(
      <ActiveOffersSection
        currentSub={null}
        onOpenTransfer={vi.fn()}
        onRefresh={vi.fn()}
        onSelectOffer={vi.fn()}
        refreshingUsage={false}
        selectedPlanId={null}
        visible={false}
      />,
    )
    const cmn = renderToStaticMarkup(
      <CmnSection
        autoRefresh={{ kind: 'idle', message: '' }}
        canRefresh
        cooldown={0}
        data={null}
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
        visible={false}
      />,
    )
    const footer = renderToStaticMarkup(<MainFooter visible />)
    const cartFab = renderToStaticMarkup(<CartFab count={2} onOpen={vi.fn()} total={12.3} />)

    expect(activeOffers).toContain('id="activeOffersContainer" style="display:none"')
    expect(activeOffers).toContain('id="activeOffersList" class="plan-list"')
    expect(activeOffers).toContain('id="activeEmptyState" class="empty-state"')
    expect(cmn).toContain('id="cmnContainer" style="display:none"')
    expect(cmn).toContain('更改电话号码服务')
    expect(footer).toContain('id="mainFooter" class="footer-note-main"')
    expect(footer).toContain('href="https://example.invalid/support"')
    expect(cartFab).toContain('<button type="button" id="cartFab" class="cart-fab" style="display:flex"')
    expect(cartFab).toContain('aria-label="打开购物车，2 件商品，总计 $12.3"')
    expect(cartFab).toContain('id="cartTotalPreview">$12.3</span>')
  })

  it('preserves purchase, cart, account-switch, and transfer body markup', () => {
    const purchase = renderToStaticMarkup(
      <PurchaseModalContent
        balance="20"
        draft={{
          title: '测试商品',
          price: 30,
          txnAmount: 20,
          paymentType: 'ALCN',
          submitting: false,
          source: 'cart',
          newLine: true,
        }}
        onChangeDraft={vi.fn()}
        showNewLineOption
      />,
    )
    const cart = renderToStaticMarkup(
      <CartModalContent
        cart={[{ offerId: 'offer-1', name: '测试套餐', price: 5, quantity: 2 }]}
        onRemove={vi.fn()}
        onUpdateQuantity={vi.fn()}
        total={10}
      />,
    )
    const account = renderToStaticMarkup(
      <AccountSwitchModalContent
        availableAccounts={[{ identifier: 'other@example.com', active: false, subBrand: '3HK' }]}
        currentSubId="sub-1"
        onAddAccount={vi.fn()}
        onSwitchAccount={vi.fn()}
        onSwitchSubscription={vi.fn()}
        subscriptions={[{ subscriptionId: 'sub-1', mobile: '61234567', status: 'ACTIVE', brand: '3HK' }]}
      />,
    )
    const transfer = renderToStaticMarkup(
      <TransferModalContent
        amount=""
        draft={{
          userOfferId: 'offer-1',
          balanceResourceId: 'resource-1',
          unit: 'megabytes',
          minTransfer: 10,
          productFamily: 'data',
          maxValue: 100,
        }}
        error="余额不足"
        onChangeAmount={vi.fn()}
        onChangeTarget={vi.fn()}
        target=""
      />,
    )

    expect(purchase).toContain('id="modalPaySection" style="display:block"')
    expect(purchase).toContain('新开UFO')
    expect(purchase).toContain('type="button"')
    expect(purchase).toContain('aria-pressed="true"')
    expect(purchase.match(/class="pay-opt selected" type="button" aria-pressed="true"/g)).toHaveLength(1)
    expect(purchase.match(/class="pay-opt " type="button" aria-pressed="false"/g)).toHaveLength(3)
    expect(purchase).toContain('class="new-line-option selected"')
    expect(purchase).toContain('class="new-line-check"')
    expect(purchase.match(/<svg/g)).toHaveLength(1)
    expect(cart).toContain('class="cart-item-title">测试套餐</div>')
    expect(cart).toContain('<span>总计</span><span style="color:#e53e3e">$10.0</span>')
    expect(cart).toContain('aria-label="减少测试套餐数量"')
    expect(cart).toContain('aria-label="增加测试套餐数量"')
    expect(cart).toContain('aria-label="移除测试套餐"')
    expect(cart.match(/<svg/g)).toHaveLength(3)
    expect(account).toContain('添加账号')
    expect(account).toContain('class="account-status-circle tone-active"')
    expect(account).toContain('ACTIVE')
    expect(account.match(/<svg/g)).toHaveLength(6)
    expect(account.match(/type="button"/g)).toHaveLength(3)
    expect(transfer).toContain('资源转移 (MB)')
    expect(transfer).toContain('id="transErrorMsg" class="form-error-msg" style="display:block"')
    expect(transfer).toContain('class="status-message status-message--error"')
    expect(transfer).toContain('role="alert"')
    expect(transfer).toContain('<span>余额不足</span>')
    expect(transfer).not.toContain('❌')
  })

  it('preserves custom modal shell classes, handle placement, and actions order', () => {
    const html = renderToStaticMarkup(
      <CustomModal
        actions={
          <>
            <button>取消</button>
            <button>确认</button>
          </>
        }
        mode="bottom-sheet"
        onClose={vi.fn()}
        open
        title="账号管理"
      >
        <div>内容</div>
      </CustomModal>,
    )

    expect(html).toContain('id="customModal" class="modal-overlay show bottom-sheet-overlay"')
    expect(html.indexOf('class="modal-handle"')).toBeLessThan(html.indexOf('内容'))
    expect(html.indexOf('取消')).toBeLessThan(html.indexOf('确认'))
    expect(html).toContain('class="modal-actions" id="modalActions"')
    expect(html).toContain('role="dialog"')
    expect(html).toContain('aria-modal="true"')
    expect(html).toContain('aria-labelledby="customModalTitle"')
    expect(html).toContain('id="customModalTitle"')
  })
})

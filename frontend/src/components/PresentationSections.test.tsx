import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { AccountSwitchModalContent } from './AccountSwitchModalContent'
import { ActiveOffersSection } from './ActiveOffersSection'
import { CartFab } from './CartFab'
import { CartModalContent } from './CartModalContent'
import { CmnSection } from './CmnSection'
import { CustomModal } from './CustomModal'
import { HistoryModal } from './HistoryModal'
import { InboxModal } from './InboxModal'
import { MainFooter } from './MainFooter'
import { MainHeader } from './MainHeader'
import { PlanList } from './PlanList'
import { PurchaseModalContent } from './PurchaseModalContent'
import { TransferModalContent } from './TransferModalContent'
import { parseCmnPattern } from '../utils/cmnPattern'
import { splitInboxTimeTokens } from '../utils/inboxTimeTokens'

vi.mock('dompurify', () => ({
  default: {
    sanitize: (input: string): string => input
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/\s+onerror=(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, ''),
  },
}))

describe('MainPage presentation component contracts', () => {
  it('preserves the section and floating-cart markup contracts', () => {
    const activeOffers = renderToStaticMarkup(<ActiveOffersSection currentSub={null} onOpenTransfer={vi.fn()} onRefresh={vi.fn()} onSelectOffer={vi.fn()} refreshingUsage={false} selectedPlanId={null} visible={false} />)
    const cmn = renderToStaticMarkup(<CmnSection autoRefresh={{ kind: 'idle', message: '' }} canRefresh cooldown={0} data={null} error="" loading={false} numbers={[]} numbersLoading={false} onAutoRefreshCancel={vi.fn()} onAutoRefreshStart={vi.fn()} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('')} pattern="" selectedNumber={null} visible={false} />)
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
    const purchase = renderToStaticMarkup(<PurchaseModalContent balance="20" draft={{ title: '测试商品', price: 30, txnAmount: 20, paymentType: 'ALCN', submitting: false, source: 'cart', newLine: true }} onChangeDraft={vi.fn()} showNewLineOption />)
    const cart = renderToStaticMarkup(<CartModalContent cart={[{ offerId: 'offer-1', name: '测试套餐', price: 5, quantity: 2 }]} onRemove={vi.fn()} onUpdateQuantity={vi.fn()} total={10} />)
    const account = renderToStaticMarkup(<AccountSwitchModalContent availableAccounts={[{ identifier: 'other@example.com', active: false, subBrand: '3HK' }]} currentSubId="sub-1" onAddAccount={vi.fn()} onSwitchAccount={vi.fn()} onSwitchSubscription={vi.fn()} subscriptions={[{ subscriptionId: 'sub-1', mobile: '61234567', status: 'ACTIVE', brand: '3HK' }]} />)
    const transfer = renderToStaticMarkup(<TransferModalContent amount="" draft={{ userOfferId: 'offer-1', balanceResourceId: 'resource-1', unit: 'megabytes', minTransfer: 10, productFamily: 'data', maxValue: 100 }} error="余额不足" onChangeAmount={vi.fn()} onChangeTarget={vi.fn()} target="" />)

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
    const html = renderToStaticMarkup(<CustomModal actions={<><button>取消</button><button>确认</button></>} mode="bottom-sheet" onClose={vi.fn()} open title="账号管理"><div>内容</div></CustomModal>)

    expect(html).toContain('id="customModal" class="modal-overlay show bottom-sheet-overlay"')
    expect(html.indexOf('class="modal-handle"')).toBeLessThan(html.indexOf('内容'))
    expect(html.indexOf('取消')).toBeLessThan(html.indexOf('确认'))
    expect(html).toContain('class="modal-actions" id="modalActions"')
    expect(html).toContain('role="dialog"')
    expect(html).toContain('aria-modal="true"')
    expect(html).toContain('aria-labelledby="customModalTitle"')
    expect(html).toContain('id="customModalTitle"')
  })

  it('renders inbox and history as labelled dialogs with semantic record rows', () => {
    const inbox = renderToStaticMarkup(<InboxModal activeInboxIndex={null} inboxLoading={false} inboxMessages={[{ subject: '通知', content: '内容', post_dt: '2026-07-12T10:00:00+08:00', intended_subscription_id: 'sub-1' }]} inboxOpen onClose={vi.fn()} onRefresh={vi.fn()} onSelectMessage={vi.fn()} subscriptions={[]} />)
    const history = renderToStaticMarkup(<HistoryModal histEnd="2026-07-12" histStart="2026-07-01" historyDetailIndex={null} historyItems={[{ transactionDate: '2026-07-12T10:00:00', type: '测试' }]} historyLoading={false} historyOpen onChangeEnd={vi.fn()} onChangeStart={vi.fn()} onClose={vi.fn()} onQuery={vi.fn()} onSelectDetail={vi.fn()} />)

    for (const html of [inbox, history]) {
      expect(html).toContain('role="dialog"')
      expect(html).toContain('aria-modal="true"')
      expect(html).toContain('records-modal-overlay')
      expect(html).toContain('class="modal-box records-modal-box"')
      expect(html).toContain('<ul class="records-list"')
      expect(html).toContain('<li class="records-list-item"')
      expect(html).toContain('<button type="button" class="records-row"')
      expect(html).toContain('data-ui-icon="chevron-right"')
      expect(html).not.toContain('role="button"')
      expect(html).not.toContain('tabindex="0"')
    }
    expect(inbox).toContain('aria-labelledby="inboxModalTitle"')
    expect(inbox).toContain('id="inboxModalTitle"')
    expect(inbox).toContain('共 1 条消息')
    expect(history).toContain('aria-labelledby="historyModalTitle"')
    expect(history).toContain('id="historyModalTitle"')
    expect(history).toContain('共 1 条记录')
    expect(history).toContain('<form class="records-filter"')
    expect(history).toContain('<label for="histStart"')
    expect(history).toContain('<label for="histEnd"')
  })

  it('integrates back navigation into record detail headers and preserves zero amounts', () => {
    const inbox = renderToStaticMarkup(<InboxModal activeInboxIndex={0} inboxLoading={false} inboxMessages={[{ subject: '服务通知', content: '<p>已处理</p>', post_dt: '2026-07-12T10:00:00+08:00', intended_subscription_id: 'sub-1' }]} inboxOpen onClose={vi.fn()} onRefresh={vi.fn()} onSelectMessage={vi.fn()} subscriptions={[{ subscriptionId: 'sub-1', mobile: '61234567' }]} />)
    const history = renderToStaticMarkup(<HistoryModal histEnd="2026-07-12" histStart="2026-07-01" historyDetailIndex={0} historyItems={[{ transactionDate: '2026-07-12T10:00:00', type: '测试', purchase: { purchaseType: 'SOSIM_VAS', purchaseStatus: 'SUCCESS', purchaseId: 'order-1', paymentDetail: { amnt: 0 }, purchaseSubscriptions: [{ offers: [{ offerNameChi: '本地数据组合' }] }] } }]} historyLoading={false} historyOpen onChangeEnd={vi.fn()} onChangeStart={vi.fn()} onClose={vi.fn()} onQuery={vi.fn()} onSelectDetail={vi.fn()} />)

    expect(inbox).toContain('class="records-modal-header records-detail-header"')
    expect(inbox).toContain('aria-label="返回收件箱"')
    expect(inbox).not.toContain('inbox-back-header')
    expect(inbox).toContain('class="records-detail-meta"')
    expect(inbox).toContain('class="inbox-detail records-detail-surface"')
    expect(history).toContain('class="records-modal-header records-detail-header"')
    expect(history).toContain('aria-label="返回交易记录"')
    expect(history).not.toContain('inbox-back-header')
    expect(history).toContain('本地数据组合')
    expect(history).toContain('$0.0')
    expect(history).toContain('<dl class="records-detail-list"')
  })

  it('displays totals from card and wallet payment sources', () => {
    const history = renderToStaticMarkup(<HistoryModal histEnd="2026-07-12" histStart="2026-07-01" historyDetailIndex={null} historyItems={[
      { transactionDate: '2026-07-12', type: '钱包支付', purchase: { paymentDetail: { amnt: 0, walletAmt: 8 } } },
      { transactionDate: '2026-07-12', type: '混合支付', purchase: { paymentDetail: { amnt: 3, walletAmt: 7 } } },
      { transactionDate: '2026-07-12', type: '免费交易', purchase: { paymentDetail: { amnt: 0, walletAmt: 0 } } },
      { transactionDate: '2026-07-12', type: '金额缺失', purchase: { paymentDetail: {} } },
    ]} historyLoading={false} historyOpen onChangeEnd={vi.fn()} onChangeStart={vi.fn()} onClose={vi.fn()} onQuery={vi.fn()} onSelectDetail={vi.fn()} />)

    expect(history).toContain('钱包支付</span><span class="records-row-amount">$8.0</span>')
    expect(history).toContain('混合支付</span><span class="records-row-amount">$10.0</span>')
    expect(history).toContain('免费交易</span><span class="records-row-amount">$0.0</span>')
    expect(history).toContain('金额缺失</span></span>')
  })

  it('renders every unique offer from subscription and purchase sources', () => {
    const item = { transactionDate: '2026-07-12', type: '套餐交易', purchase: { purchaseType: 'SOSIM_VAS', purchaseSubscriptions: [{ offers: [{ offerNameChi: '本地数据' }, { offerNameChi: '漫游数据' }] }, { offers: [{ offerNameChi: '本地数据' }] }], offer: [{ offerNameChi: '语音组合' }, { offerNameChi: '漫游数据' }] } }
    const list = renderToStaticMarkup(<HistoryModal histEnd="2026-07-12" histStart="2026-07-01" historyDetailIndex={null} historyItems={[item]} historyLoading={false} historyOpen onChangeEnd={vi.fn()} onChangeStart={vi.fn()} onClose={vi.fn()} onQuery={vi.fn()} onSelectDetail={vi.fn()} />)
    const detail = renderToStaticMarkup(<HistoryModal histEnd="2026-07-12" histStart="2026-07-01" historyDetailIndex={0} historyItems={[item]} historyLoading={false} historyOpen onChangeEnd={vi.fn()} onChangeStart={vi.fn()} onClose={vi.fn()} onQuery={vi.fn()} onSelectDetail={vi.fn()} />)

    expect(list).toContain('本地数据、漫游数据、语音组合')
    expect(detail).toContain('<ul class="records-offer-list"><li>本地数据</li><li>漫游数据</li><li>语音组合</li></ul>')
    expect(detail.match(/<li>本地数据<\/li>/g)).toHaveLength(1)
    expect(detail.match(/<li>漫游数据<\/li>/g)).toHaveLength(1)
  })

  it('identifies numeric Chinese time tokens without changing their text', () => {
    expect(splitInboxTimeTokens('服務有效期60天，另有2個月及30分鐘。')).toEqual([
      { text: '服務有效期', nowrap: false },
      { text: '60天', nowrap: true },
      { text: '，另有', nowrap: false },
      { text: '2個月', nowrap: true },
      { text: '及', nowrap: false },
      { text: '30分鐘', nowrap: true },
      { text: '。', nowrap: false },
    ])
  })

  it('keeps malicious inbox HTML removed before time-token post-processing', () => {
    const inbox = renderToStaticMarkup(<InboxModal activeInboxIndex={0} inboxLoading={false} inboxMessages={[{ subject: '通知', content: '<img src=x onerror=alert(1)>60天<script>alert(2)</script>', post_dt: '2026-07-12T10:00:00+08:00', intended_subscription_id: 'sub-1' }]} inboxOpen onClose={vi.fn()} onRefresh={vi.fn()} onSelectMessage={vi.fn()} subscriptions={[]} />)

    expect(inbox).toContain('<img src=x>60天')
    expect(inbox).not.toContain('onerror')
    expect(inbox).not.toContain('<script')
    expect(inbox).not.toContain('alert(2)')
  })

  it('renders semantic SVG icons without legacy character controls', () => {
    const currentSub = { subscriptionId: 'sub-1', mobile: '51234567', activeOffers: [{ offerId: 'offer-1', name: '测试套餐', endDate: '2026-12-31' }] }
    const activeOffers = renderToStaticMarkup(<ActiveOffersSection currentSub={currentSub} onOpenTransfer={vi.fn()} onRefresh={vi.fn()} onSelectOffer={vi.fn()} refreshingUsage={false} selectedPlanId="sub-offer-1" visible />)
    const cmnInitial = renderToStaticMarkup(<CmnSection autoRefresh={{ kind: 'idle', message: '' }} canRefresh cooldown={0} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={[]} numbersLoading={false} onAutoRefreshCancel={vi.fn()} onAutoRefreshStart={vi.fn()} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('')} pattern="" selectedNumber={null} visible />)
    const cmnCooldown = renderToStaticMarkup(<CmnSection autoRefresh={{ kind: 'idle', message: '' }} canRefresh={false} cooldown={8} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={['66612345']} numbersLoading={false} onAutoRefreshCancel={vi.fn()} onAutoRefreshStart={vi.fn()} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('')} pattern="" selectedNumber={null} visible />)
    const plans = renderToStaticMarkup(<PlanList filteredPlans={[{ offerId: 'offer-1', name: '测试套餐', price: 10, validity: '30日', desc: '说明', category: 'LOCAL' }]} noNumberMode={false} onAddToCart={vi.fn()} onSelectPlan={vi.fn()} plansLoading={false} selectedPlanId="offer-1" showFreePlans={false} visible />)
    const header = renderToStaticMarkup(<MainHeader availableAccounts={[{ identifier: 'account-1', active: true, subBrand: 'SoSIM' }]} balance="10" category="ALL" currentSub={currentSub} noNumberMode={false} onLogout={vi.fn()} onOpenHistory={vi.fn()} onOpenInbox={vi.fn()} onOpenSwitch={vi.fn()} onSearchChange={vi.fn()} onShowAlert={vi.fn()} onSwitchCategory={vi.fn()} search="" />)
    const html = [activeOffers, cmnInitial, cmnCooldown, plans, header].join('')

    for (const legacyIcon of ['🔍', '🔄', '⏳', '⚠️', '↻', '▼', '📅']) {
      expect(html).not.toContain(legacyIcon)
    }
    expect(cmnInitial).toContain('<svg')
    expect(cmnCooldown).toContain('<svg')
    expect(cmnCooldown).toContain('（8s）')
    expect(activeOffers).toContain('class="plan-card open"')
    expect(activeOffers).toContain('<button type="button" class="plan-card-disclosure" aria-expanded="true" aria-controls="active-offer-details-offer-1"')
    expect(activeOffers).not.toContain('<div class="plan-card open" role="button"')
    expect(activeOffers).toContain('id="active-offer-details-offer-1" class="card-details open" aria-hidden="false"')
    expect(plans).toContain('class="plan-card open"')
    expect(plans).toContain('<button type="button" class="plan-card-disclosure" aria-expanded="true" aria-controls="plan-details-offer-1"')
    expect(plans).not.toContain('<div class="plan-card open" role="button"')
    expect(plans).toContain('id="plan-details-offer-1" class="card-details open" aria-hidden="false"')
    expect(header).toContain('id="u_switch_hint"')
    expect(header).toContain('<button type="button" id="u_switch_hint"')
    expect(header).toContain('<button type="button" class="cat-tab active"')
    expect(header).not.toContain('role="button"')
    expect(header).not.toContain('tabindex="0"')
  })

  it('removes collapsed disclosure controls from the tab order without unmounting animated details', () => {
    const plans = renderToStaticMarkup(<PlanList filteredPlans={[{ offerId: 'offer-1', name: '测试套餐', price: 10, validity: '30日', desc: '说明', category: 'LOCAL' }]} noNumberMode={false} onAddToCart={vi.fn()} onSelectPlan={vi.fn()} plansLoading={false} selectedPlanId={null} showFreePlans={false} visible />)
    const currentSub = { subscriptionId: 'sub-1', mobile: '51234567', activeOffers: [{ offerId: 'offer-1', name: '测试套餐', endDate: '2026-12-31', usage: [{ name: '数据', canTransfer: true, balanceResourceId: 'resource-1', unit: 'megabytes', minTransfer: 10, productFamily: 'data', remain: 100 }] }] }
    const activeOffers = renderToStaticMarkup(<ActiveOffersSection currentSub={currentSub} onOpenTransfer={vi.fn()} onRefresh={vi.fn()} onSelectOffer={vi.fn()} refreshingUsage={false} selectedPlanId={null} visible />)

    expect(plans).toContain('id="plan-details-offer-1" class="card-details " aria-hidden="true" inert=""')
    expect(plans).toContain('加入购物车')
    expect(activeOffers).toContain('id="active-offer-details-offer-1" class="card-details " aria-hidden="true" inert=""')
    expect(activeOffers).toContain('>转移</button>')
  })

  it('renders at most nine CMN candidates for a three-by-three grid', () => {
    const numbers = Array.from({ length: 10 }, (_, index) => String(60000000 + index))
    const html = renderToStaticMarkup(<CmnSection autoRefresh={{ kind: 'idle', message: '' }} canRefresh cooldown={0} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={numbers} numbersLoading={false} onAutoRefreshCancel={vi.fn()} onAutoRefreshStart={vi.fn()} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('6[0-9]{2}')} pattern="6[0-9]{2}" selectedNumber={null} visible />)

    expect((html.match(/class="num-btn /g) || []).length).toBe(9)
    expect(html).not.toContain(numbers[9])
  })

  it('renders accessible safe-pattern search, auto-refresh guidance, and React mark nodes', () => {
    const numbers = ['66612345', '12345666', '88888888', '10000000', '20000000', '30000000', '40000000', '50000000', '60000000']
    const html = renderToStaticMarkup(<CmnSection autoRefresh={{ kind: 'idle', message: '' }} canRefresh cooldown={0} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={numbers} numbersLoading={false} onAutoRefreshCancel={vi.fn()} onAutoRefreshStart={vi.fn()} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('666')} pattern="666" selectedNumber="66612345" visible />)

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
    const html = renderToStaticMarkup(<CmnSection autoRefresh={{ kind: 'idle', message: '' }} canRefresh cooldown={0} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={['66612345']} numbersLoading={false} onAutoRefreshCancel={vi.fn()} onAutoRefreshStart={vi.fn()} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern(pattern)} pattern={pattern} selectedNumber={null} visible />)

    expect(html).toContain('role="alert"')
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;')
    expect(html).not.toContain('<img')
    expect(html).not.toContain('class="cmn-match"')
  })

  it('renders valid-pattern guidance and running cancel state with atomic status semantics', () => {
    const idle = renderToStaticMarkup(<CmnSection autoRefresh={{ kind: 'idle', message: '' }} canRefresh cooldown={0} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={['12345678']} numbersLoading={false} onAutoRefreshCancel={vi.fn()} onAutoRefreshStart={vi.fn()} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('666')} pattern="666" selectedNumber={null} visible />)
    const running = renderToStaticMarkup(<CmnSection autoRefresh={{ kind: 'running', attempt: 4, message: '正在自动查找第 4 批号码' }} canRefresh={false} cooldown={2} data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }} error="" loading={false} numbers={['12345678']} numbersLoading onAutoRefreshCancel={vi.fn()} onAutoRefreshStart={vi.fn()} onPatternChange={vi.fn()} onRefresh={vi.fn()} onSelectNumber={vi.fn()} onSubmit={vi.fn()} parsedPattern={parseCmnPattern('666')} pattern="666" selectedNumber={null} visible />)

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
    expect(running).toContain('id="cmn-auto-refresh-status" class="cmn-auto-refresh-status" role="status" aria-live="polite" aria-atomic="true"')
  })
})

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { splitInboxTimeTokens } from '@/utils/inboxTimeTokens'
import { HistoryModal } from './HistoryModal'
import { InboxModal } from './InboxModal'

vi.mock('dompurify', () => ({
  default: {
    sanitize: (input: string): string =>
      input.replace(/<script[\s\S]*?<\/script>/gi, '').replace(/\s+onerror=(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, ''),
  },
}))

describe('records presentation contracts', () => {
  it('renders inbox and history as labelled dialogs with semantic record rows', () => {
    const inbox = renderToStaticMarkup(
      <InboxModal
        activeInboxIndex={null}
        inboxLoading={false}
        inboxMessages={[
          { subject: '通知', content: '内容', post_dt: '2026-07-12T10:00:00+08:00', intended_subscription_id: 'sub-1' },
        ]}
        inboxOpen
        onClose={vi.fn()}
        onRefresh={vi.fn()}
        onSelectMessage={vi.fn()}
        subscriptions={[]}
      />,
    )
    const history = renderToStaticMarkup(
      <HistoryModal
        histEnd="2026-07-12"
        histStart="2026-07-01"
        historyDetailIndex={null}
        historyItems={[{ transactionDate: '2026-07-12T10:00:00', type: '测试' }]}
        historyLoading={false}
        historyOpen
        onChangeEnd={vi.fn()}
        onChangeStart={vi.fn()}
        onClose={vi.fn()}
        onQuery={vi.fn()}
        onSelectDetail={vi.fn()}
      />,
    )

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
    const inbox = renderToStaticMarkup(
      <InboxModal
        activeInboxIndex={0}
        inboxLoading={false}
        inboxMessages={[
          {
            subject: '服务通知',
            content: '<p>已处理</p>',
            post_dt: '2026-07-12T10:00:00+08:00',
            intended_subscription_id: 'sub-1',
          },
        ]}
        inboxOpen
        onClose={vi.fn()}
        onRefresh={vi.fn()}
        onSelectMessage={vi.fn()}
        subscriptions={[{ subscriptionId: 'sub-1', mobile: '61234567' }]}
      />,
    )
    const history = renderToStaticMarkup(
      <HistoryModal
        histEnd="2026-07-12"
        histStart="2026-07-01"
        historyDetailIndex={0}
        historyItems={[
          {
            transactionDate: '2026-07-12T10:00:00',
            type: '测试',
            purchase: {
              purchaseType: 'SOSIM_VAS',
              purchaseStatus: 'SUCCESS',
              purchaseId: 'order-1',
              paymentDetail: { amnt: 0 },
              purchaseSubscriptions: [{ offers: [{ offerNameChi: '本地数据组合' }] }],
            },
          },
        ]}
        historyLoading={false}
        historyOpen
        onChangeEnd={vi.fn()}
        onChangeStart={vi.fn()}
        onClose={vi.fn()}
        onQuery={vi.fn()}
        onSelectDetail={vi.fn()}
      />,
    )

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
    const history = renderToStaticMarkup(
      <HistoryModal
        histEnd="2026-07-12"
        histStart="2026-07-01"
        historyDetailIndex={null}
        historyItems={[
          { transactionDate: '2026-07-12', type: '钱包支付', purchase: { paymentDetail: { amnt: 0, walletAmt: 8 } } },
          { transactionDate: '2026-07-12', type: '混合支付', purchase: { paymentDetail: { amnt: 3, walletAmt: 7 } } },
          { transactionDate: '2026-07-12', type: '免费交易', purchase: { paymentDetail: { amnt: 0, walletAmt: 0 } } },
          { transactionDate: '2026-07-12', type: '金额缺失', purchase: { paymentDetail: {} } },
        ]}
        historyLoading={false}
        historyOpen
        onChangeEnd={vi.fn()}
        onChangeStart={vi.fn()}
        onClose={vi.fn()}
        onQuery={vi.fn()}
        onSelectDetail={vi.fn()}
      />,
    )

    expect(history).toContain('钱包支付</span><span class="records-row-amount">$8.0</span>')
    expect(history).toContain('混合支付</span><span class="records-row-amount">$10.0</span>')
    expect(history).toContain('免费交易</span><span class="records-row-amount">$0.0</span>')
    expect(history).toContain('金额缺失</span></span>')
  })

  it('renders every unique offer from subscription and purchase sources', () => {
    const item = {
      transactionDate: '2026-07-12',
      type: '套餐交易',
      purchase: {
        purchaseType: 'SOSIM_VAS',
        purchaseSubscriptions: [
          { offers: [{ offerNameChi: '本地数据' }, { offerNameChi: '漫游数据' }] },
          { offers: [{ offerNameChi: '本地数据' }] },
        ],
        offer: [{ offerNameChi: '语音组合' }, { offerNameChi: '漫游数据' }],
      },
    }
    const list = renderToStaticMarkup(
      <HistoryModal
        histEnd="2026-07-12"
        histStart="2026-07-01"
        historyDetailIndex={null}
        historyItems={[item]}
        historyLoading={false}
        historyOpen
        onChangeEnd={vi.fn()}
        onChangeStart={vi.fn()}
        onClose={vi.fn()}
        onQuery={vi.fn()}
        onSelectDetail={vi.fn()}
      />,
    )
    const detail = renderToStaticMarkup(
      <HistoryModal
        histEnd="2026-07-12"
        histStart="2026-07-01"
        historyDetailIndex={0}
        historyItems={[item]}
        historyLoading={false}
        historyOpen
        onChangeEnd={vi.fn()}
        onChangeStart={vi.fn()}
        onClose={vi.fn()}
        onQuery={vi.fn()}
        onSelectDetail={vi.fn()}
      />,
    )

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
    const inbox = renderToStaticMarkup(
      <InboxModal
        activeInboxIndex={0}
        inboxLoading={false}
        inboxMessages={[
          {
            subject: '通知',
            content: '<img src=x onerror=alert(1)>60天<script>alert(2)</script>',
            post_dt: '2026-07-12T10:00:00+08:00',
            intended_subscription_id: 'sub-1',
          },
        ]}
        inboxOpen
        onClose={vi.fn()}
        onRefresh={vi.fn()}
        onSelectMessage={vi.fn()}
        subscriptions={[]}
      />,
    )

    expect(inbox).toContain('<img src=x>60天')
    expect(inbox).not.toContain('onerror')
    expect(inbox).not.toContain('<script')
    expect(inbox).not.toContain('alert(2)')
  })
})

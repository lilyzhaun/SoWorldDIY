import { useEffect, useRef } from 'react'

import { useDialogAccessibility } from '@/hooks/useDialogAccessibility'
import type { HistoryItem } from '@/types'
import { UiIcon } from './UiIcon'

type HistoryModalProps = {
  readonly histEnd: string
  readonly histStart: string
  readonly historyDetailIndex: number | null
  readonly historyItems: HistoryItem[]
  readonly historyLoading: boolean
  readonly historyOpen: boolean
  readonly onChangeEnd: (value: string) => void
  readonly onChangeStart: (value: string) => void
  readonly onClose: () => void
  readonly onQuery: () => void
  readonly onSelectDetail: (index: number | null) => void
}

function formatHistoryDate(value?: string): string {
  return (value ?? '').replace('T', ' ').split('.')[0]
}

function getOfferNames(item: HistoryItem): string[] {
  const offers = [
    ...(item.purchase?.purchaseSubscriptions?.flatMap((subscription) => subscription.offers ?? []) ?? []),
    ...(item.purchase?.offer ?? []),
  ]
  const names = offers.flatMap((offer) => {
    const name = offer.offerNameChi ?? offer.offerName
    return name ? [name] : []
  })
  return [...new Set(names)]
}

function getHistoryTitle(item: HistoryItem): string {
  const offerName = getOfferNames(item).join('、')
  if (item.purchase?.purchaseType === 'PREPAID_RECHARGE') return '充值'
  if (item.purchase?.purchaseType === 'SOSIM_VAS') return offerName || '购买套餐'
  return offerName || item.type || item.purchase?.purchaseType || '交易记录'
}

function getAmount(item: HistoryItem): number | null {
  const paymentDetail = item.purchase?.paymentDetail
  if (!paymentDetail) return null
  const amounts = [paymentDetail.amnt, paymentDetail.walletAmt].filter((amount): amount is number => amount !== undefined)
  return amounts.length === 0 ? null : amounts.reduce((total, amount) => total + amount, 0)
}

export function HistoryModal({
  histEnd,
  histStart,
  historyDetailIndex,
  historyItems,
  historyLoading,
  historyOpen,
  onChangeEnd,
  onChangeStart,
  onClose,
  onQuery,
  onSelectDetail,
}: HistoryModalProps): JSX.Element {
  const historyDetail = historyDetailIndex === null ? null : historyItems[historyDetailIndex] ?? null
  const dialogRef = useDialogAccessibility(historyOpen, onClose)
  const backButtonRef = useRef<HTMLButtonElement>(null)
  const rowRefs = useRef<Array<HTMLButtonElement | null>>([])
  const previousIndexRef = useRef<number | null>(null)

  useEffect(() => {
    const previousIndex = previousIndexRef.current
    previousIndexRef.current = historyDetailIndex
    if (historyDetailIndex !== null) backButtonRef.current?.focus()
    else if (previousIndex !== null) rowRefs.current[previousIndex]?.focus()
  }, [historyDetailIndex])

  const detailTitle = historyDetail ? getHistoryTitle(historyDetail) : ''
  const detailAmount = historyDetail ? getAmount(historyDetail) : null
  const detailDate = formatHistoryDate(historyDetail?.transactionDate)
  const detailStatus = historyDetail?.purchase?.purchaseStatus
  const detailType = historyDetail?.purchase?.purchaseType ?? historyDetail?.type
  const detailOrder = historyDetail?.purchase?.purchaseId
  const detailOffers = historyDetail ? getOfferNames(historyDetail) : []

  return (
    <div ref={dialogRef} id="historyModal" className={`modal-overlay records-modal-overlay ${historyOpen ? 'show' : ''}`} role="dialog" aria-modal="true" aria-labelledby="historyModalTitle" onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div className="modal-box records-modal-box">
        {historyDetail ? (
          <>
            <header className="records-modal-header records-detail-header">
              <button ref={backButtonRef} type="button" className="records-back-btn" aria-label="返回交易记录" onClick={() => onSelectDetail(null)}><UiIcon name="arrow-left" size={18} /></button>
              <div className="records-header-copy">
                <h2 className="records-modal-title records-detail-title" id="historyModalTitle">{detailTitle}</h2>
                <p className="records-modal-subtitle">{detailDate}{detailStatus ? ` · ${detailStatus}` : ''}</p>
              </div>
              <button type="button" className="modal-icon-btn" aria-label="关闭交易记录" onClick={onClose}><UiIcon name="close" /></button>
            </header>
            <div id="historyContent" className="records-modal-content records-detail-content">
              {detailAmount !== null ? <div className="records-amount-summary"><strong>${detailAmount.toFixed(1)}</strong><span>交易金额</span></div> : null}
              <dl className="records-detail-list">
                {detailType ? <div><dt>类型</dt><dd>{detailType}</dd></div> : null}
                {detailStatus ? <div><dt>状态</dt><dd><span className="records-status-badge">{detailStatus}</span></dd></div> : null}
                {detailDate ? <div><dt>时间</dt><dd>{detailDate}</dd></div> : null}
                {detailOrder ? <div><dt>单号</dt><dd className="records-technical-token">{detailOrder}</dd></div> : null}
                {detailOffers.length > 0 ? <div><dt>套餐</dt><dd><ul className="records-offer-list">{detailOffers.map((offerName) => <li key={offerName}>{offerName}</li>)}</ul></dd></div> : null}
              </dl>
            </div>
          </>
        ) : (
          <>
            <header className="records-modal-header">
              <div className="records-header-copy">
                <h2 className="records-modal-title" id="historyModalTitle">交易记录</h2>
                <p className="records-modal-subtitle">共 {historyItems.length} 条记录</p>
              </div>
              <button type="button" className="modal-icon-btn" data-dialog-initial-focus aria-label="关闭交易记录" onClick={onClose}><UiIcon name="close" /></button>
            </header>
            <form className="records-filter" onSubmit={(event) => { event.preventDefault(); onQuery() }}>
              <label htmlFor="histStart"><span>开始日期</span><input type="date" id="histStart" className="date-input" value={histStart} onChange={(event) => onChangeStart(event.target.value)} /></label>
              <label htmlFor="histEnd"><span>结束日期</span><input type="date" id="histEnd" className="date-input" value={histEnd} onChange={(event) => onChangeEnd(event.target.value)} /></label>
              <button type="submit" className="filter-btn" disabled={historyLoading}>{historyLoading ? '查询中…' : '查询'}</button>
            </form>
            <div id="historyContent" className="records-modal-content">
              {historyLoading ? <div className="records-state loader">加载中…</div> : historyItems.length === 0 ? <div className="records-state empty-state">该时段无交易记录</div> : (
                <ul className="records-list">
                  {historyItems.map((item, index) => {
                    const title = getHistoryTitle(item)
                    const date = formatHistoryDate(item.transactionDate)
                    const status = item.purchase?.purchaseStatus
                    const amount = getAmount(item)
                    return (
                      <li key={`${title}-${index}`} className="records-list-item">
                        <button ref={(element) => { rowRefs.current[index] = element }} type="button" className="records-row" onClick={() => onSelectDetail(index)}>
                          <span className="records-row-copy">
                            <span className="records-row-heading"><span className="records-row-title">{title}</span>{amount !== null ? <span className="records-row-amount">${amount.toFixed(1)}</span> : null}</span>
                            <span className="records-row-meta"><time>{date}</time>{status ? <span className="records-status-badge">{status}</span> : null}</span>
                          </span>
                          <UiIcon className="records-row-chevron" name="chevron-right" size={18} />
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

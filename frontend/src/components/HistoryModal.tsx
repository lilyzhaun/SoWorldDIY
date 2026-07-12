import type { HistoryItem } from '../types'
import { useDialogAccessibility } from '../hooks/useDialogAccessibility'
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
  const historyDetail = historyDetailIndex !== null ? historyItems[historyDetailIndex] : null
  const dialogRef = useDialogAccessibility(historyOpen, onClose)

  return (
    <div ref={dialogRef} id="historyModal" className={`modal-overlay ${historyOpen ? 'show' : ''}`} role="dialog" aria-modal="true" aria-labelledby="historyModalTitle" onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div className="modal-box" style={{ maxWidth: '400px', padding: '20px 0', height: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '0 20px 15px 20px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <div className="modal-title" id="historyModalTitle" style={{ margin: 0 }}>交易记录</div>
          <button type="button" className="modal-icon-btn" data-dialog-initial-focus aria-label="关闭交易记录" onClick={onClose}><UiIcon name="close" /></button>
        </div>
        <div className="history-filter-bar">
          <input type="date" id="histStart" className="date-input" value={histStart} onChange={(event) => onChangeStart(event.target.value)} />
          <span style={{ color: '#94a3b8' }}>至</span>
          <input type="date" id="histEnd" className="date-input" value={histEnd} onChange={(event) => onChangeEnd(event.target.value)} />
          <button type="button" className="filter-btn" disabled={historyLoading} onClick={onQuery}>{historyLoading ? '查询中…' : '查询'}</button>
        </div>
        <div id="historyContent" style={{ padding: 0, flex: 1, overflowY: 'auto' }}>
          {historyLoading ? <div className="loader" style={{ padding: '20px' }}>加载中…</div> : historyDetail ? (
            <div style={{ padding: 0 }}>
              <button type="button" className="inbox-back-header" onClick={() => onSelectDetail(null)}><UiIcon name="arrow-left" size={16} /> <span>返回</span></button>
              <div style={{ padding: '0 20px' }}>
                <div style={{ fontSize: '24px', fontWeight: 800, textAlign: 'center' }}>${Number(historyDetail.purchase?.paymentDetail?.amnt || 0).toFixed(1)}</div>
                <div style={{ textAlign: 'center', fontSize: '13px', color: 'var(--text-sub)', marginBottom: '20px' }}>交易金额</div>
                <div className="cart-list" style={{ padding: 0 }}>
                  <div className="cart-item"><span>状态</span><span>{historyDetail.purchase?.purchaseStatus || '--'}</span></div>
                  <div className="cart-item"><span>时间</span><span>{(historyDetail.transactionDate || '').replace('T', ' ')}</span></div>
                  <div className="cart-item"><span>单号</span><span>{historyDetail.purchase?.purchaseId || '--'}</span></div>
                </div>
              </div>
            </div>
          ) : historyItems.length === 0 ? <div className="empty-state">该时段无交易记录</div> : (
            <div className="inbox-list-container">
              {historyItems.map((item, index) => {
                const p = item.purchase || {}
                const dateStr = (item.transactionDate || '').replace('T', ' ').split('.')[0]
                const status = p.purchaseStatus || 'UNKNOWN'
                const statusColor = status === 'SUCCESS' ? '#10b981' : (status === 'CANCEL' || status === 'FAILED' ? '#e53e3e' : '#f59e0b')
                const amount = p.paymentDetail ? (p.paymentDetail.amnt || p.paymentDetail.walletAmt || 0) : 0
                const title = p.purchaseType === 'PREPAID_RECHARGE' ? '充值' : (p.purchaseType === 'SOSIM_VAS' ? '购买套餐' : item.type || '未知')
                return (
                  <div key={`${title}-${index}`} className="inbox-item" role="button" tabIndex={0} onClick={() => onSelectDetail(index)} onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onSelectDetail(index) } }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><div style={{ fontWeight: 600 }}>{title}</div><div style={{ fontWeight: 700, color: statusColor }}>${Number(amount).toFixed(1)}</div></div>
                    <div className="inbox-meta"><span>{dateStr}</span><span>{status}</span></div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

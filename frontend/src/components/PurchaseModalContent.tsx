import type { PurchaseDraft } from '@/hooks/usePurchaseCart'
import { UiIcon } from './UiIcon'

type PurchaseModalContentProps = {
  readonly balance: string
  readonly draft: PurchaseDraft
  readonly onChangeDraft: React.Dispatch<React.SetStateAction<PurchaseDraft | null>>
  readonly showNewLineOption: boolean
}

export function PurchaseModalContent({ balance, draft, onChangeDraft, showNewLineOption }: PurchaseModalContentProps): JSX.Element {
  const currentBalance = Number.parseFloat(balance) || 0
  const maxAllowed = Math.min(currentBalance, draft.price)
  const validTxn = Math.max(0, Math.min(draft.txnAmount, maxAllowed))
  const payAmount = Math.max(0, draft.price - validTxn)
  return (
    <div style={{ textAlign: 'left' }}>
      <div style={{ fontSize: '14px', color: '#64748b' }}>商品信息</div>
      <div style={{ fontWeight: 700, fontSize: '16px', marginBottom: '15px', borderBottom: '1px solid #eee', paddingBottom: '10px' }}>{draft.title}</div>
      {showNewLineOption ? (
        <button type="button" className={`new-line-option${draft.newLine ? ' selected' : ''}`} aria-pressed={draft.newLine} onClick={() => onChangeDraft((previous) => (previous ? { ...previous, newLine: !previous.newLine } : null))}>
          <span aria-hidden="true" className="new-line-check">{draft.newLine ? <UiIcon name="check" size={16} /> : null}</span>
          <span><span className="new-line-title">新开UFO</span><span className="new-line-copy">新开号码(GLOBAL_ESIM)</span></span>
        </button>
      ) : null}
      <div style={{ marginBottom: '15px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}><span>余额抵扣</span><span style={{ color: '#64748b' }}>(可用: ${currentBalance})</span></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}><span style={{ fontWeight: 'bold' }}>$</span><input type="number" value={validTxn} step="0.1" max={maxAllowed} min={0} onChange={(event) => { const next = Number.parseFloat(event.target.value); onChangeDraft((previous) => (previous ? { ...previous, txnAmount: Number.isNaN(next) ? 0 : next } : null)) }} style={{ width: '100%', padding: '10px', border: '1px solid #cbd5e1', borderRadius: '8px', fontWeight: 700 }} /></div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', fontWeight: 700 }}><span>需支付</span><span style={{ fontSize: '18px', color: '#e53e3e' }}>${payAmount.toFixed(1)}</span></div>
      <div id="modalPaySection" style={{ display: payAmount > 0.01 ? 'block' : 'none' }}>
        <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '8px' }}>补款方式</div>
        <div className="payment-grid">{(['ALCN', 'ALHK', 'WECHAT', 'MPGS'] as const).map((item) => <button key={item} className={`pay-opt ${draft.paymentType === item ? 'selected' : ''}`} type="button" aria-pressed={draft.paymentType === item} onClick={() => onChangeDraft((previous) => (previous ? { ...previous, paymentType: item } : null))}>{item === 'ALCN' ? '支付宝' : item === 'ALHK' ? 'AlipayHK' : item === 'WECHAT' ? '微信' : '信用卡'}</button>)}</div>
      </div>
    </div>
  )
}

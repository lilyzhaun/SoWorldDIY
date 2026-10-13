import type { PurchaseDraft } from '@/hooks/usePurchaseCart'
import type { ModalKind } from '@/hooks/useAppModal'

type MainModalActionsProps = {
  readonly modalKind: ModalKind
  readonly purchaseDraft: PurchaseDraft | null
  readonly transferSubmitting: boolean
  readonly onClose: () => void
  readonly onCheckout: () => void
  readonly onConfirmPurchase: () => void
  readonly onConfirmTransfer: () => void
}

export function MainModalActions({
  modalKind,
  purchaseDraft,
  transferSubmitting,
  onClose,
  onCheckout,
  onConfirmPurchase,
  onConfirmTransfer,
}: MainModalActionsProps): React.JSX.Element {
  if (modalKind === 'alert') {
    return (
      <button className="modal-btn confirm alert-ok" onClick={onClose}>
        关闭
      </button>
    )
  }
  if (modalKind === 'switch') {
    return <></>
  }
  if (modalKind === 'cart') {
    return (
      <>
        <button className="modal-btn cancel" onClick={onClose}>
          取消
        </button>
        <button className="modal-btn confirm" onClick={onCheckout}>
          去结算
        </button>
      </>
    )
  }
  if (modalKind === 'purchase') {
    return (
      <>
        <button className="modal-btn cancel" onClick={onClose}>
          取消
        </button>
        <button className="modal-btn confirm" disabled={purchaseDraft?.submitting} onClick={onConfirmPurchase}>
          {purchaseDraft?.submitting ? '提交中…' : '确认'}
        </button>
      </>
    )
  }
  if (modalKind === 'transfer') {
    return (
      <>
        <button className="modal-btn cancel" onClick={onClose}>
          取消
        </button>
        <button className="modal-btn confirm" disabled={transferSubmitting} onClick={onConfirmTransfer}>
          {transferSubmitting ? '处理中…' : '确认转移'}
        </button>
      </>
    )
  }
  return <></>
}

import type { CartItem } from '@/types'
import { isRootOpacityTransition, type PresencePhase } from '@/hooks/usePresenceValue'
import type { CartQuantityDraft } from '@/hooks/usePurchaseCart'
import { useDialogAccessibility } from '@/hooks/useDialogAccessibility'
import { UiIcon } from './UiIcon'

type CartQuantityModalProps = {
  readonly cart: CartItem[]
  readonly draft: CartQuantityDraft
  readonly onExitComplete: () => void
  readonly onCancel: () => void
  readonly onConfirm: () => void
  readonly onUpdateDraft: (draft: CartQuantityDraft) => void
  readonly phase: Exclude<PresencePhase, 'unmounted'>
}

export function CartQuantityModal({
  cart,
  draft,
  onCancel,
  onConfirm,
  onExitComplete,
  onUpdateDraft,
  phase,
}: CartQuantityModalProps): JSX.Element {
  const entered = phase === 'entered'
  const dialogRef = useDialogAccessibility(true, onCancel)
  return (
    <div
      ref={dialogRef}
      id="cartQuantityModal"
      className={`modal-overlay ${entered ? 'show' : 'is-exiting'}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cartQuantityModalTitle"
      data-dialog-accessibility-active="true"
      onClick={(event) => {
        if (entered && event.target === event.currentTarget) onCancel()
      }}
      onTransitionEnd={(event) => {
        if (isRootOpacityTransition(event)) onExitComplete()
      }}
    >
      <div className="modal-box">
        <div className="modal-title" id="cartQuantityModalTitle">
          {cart.some((item) => item.offerId === draft.offerId) ? '调整数量' : '加入购物车'}
        </div>
        <div className="modal-text" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '14px', color: '#64748b' }}>{draft.name}</div>
          <div style={{ fontSize: '20px', fontWeight: 800, color: '#FF7B00', margin: '10px 0' }}>
            ${draft.price} / 件
          </div>
          <div className="qty-selector">
            <button
              type="button"
              className="qty-btn"
              aria-label="减少数量"
              onClick={() => onUpdateDraft({ ...draft, quantity: Math.max(1, draft.quantity - 1) })}
            >
              <UiIcon name="minus" size={16} />
            </button>
            <input
              type="number"
              className="qty-input"
              value={draft.quantity}
              min={1}
              max={99}
              onChange={(event) =>
                onUpdateDraft({
                  ...draft,
                  quantity: Math.max(1, Math.min(99, Number.parseInt(event.target.value || '1', 10) || 1)),
                })
              }
            />
            <button
              type="button"
              className="qty-btn"
              aria-label="增加数量"
              onClick={() => onUpdateDraft({ ...draft, quantity: Math.min(99, draft.quantity + 1) })}
            >
              <UiIcon name="plus" size={16} />
            </button>
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="modal-btn cancel" data-dialog-initial-focus onClick={onCancel}>
            取消
          </button>
          <button type="button" className="modal-btn confirm" onClick={onConfirm}>
            确定
          </button>
        </div>
      </div>
    </div>
  )
}

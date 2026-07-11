import type { CartItem } from '../types'

type CartQuantityDraft = {
  readonly offerId: string
  readonly name: string
  readonly price: number
  readonly quantity: number
}

type CartQuantityModalProps = {
  readonly cart: CartItem[]
  readonly draft: CartQuantityDraft
  readonly onCancel: () => void
  readonly onConfirm: () => void
  readonly onUpdateDraft: (draft: CartQuantityDraft) => void
}

export function CartQuantityModal({ cart, draft, onCancel, onConfirm, onUpdateDraft }: CartQuantityModalProps): JSX.Element {
  return (
    <div id="customModal" className="modal-overlay show" onClick={(event) => { if (event.target === event.currentTarget) onCancel() }}>
      <div className="modal-box">
        <div className="modal-title">{cart.some((item) => item.offerId === draft.offerId) ? '调整数量' : '加入购物车'}</div>
        <div className="modal-text" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '14px', color: '#64748b' }}>{draft.name}</div>
          <div style={{ fontSize: '20px', fontWeight: 800, color: '#FF7B00', margin: '10px 0' }}>${draft.price} / 件</div>
          <div className="qty-selector"><button className="qty-btn" onClick={() => onUpdateDraft({ ...draft, quantity: Math.max(1, draft.quantity - 1) })}>-</button><input type="number" className="qty-input" value={draft.quantity} min={1} max={99} onChange={(event) => onUpdateDraft({ ...draft, quantity: Math.max(1, Math.min(99, Number.parseInt(event.target.value || '1', 10) || 1)) })} /><button className="qty-btn" onClick={() => onUpdateDraft({ ...draft, quantity: Math.min(99, draft.quantity + 1) })}>+</button></div>
        </div>
        <div className="modal-actions"><button className="modal-btn cancel" onClick={onCancel}>取消</button><button className="modal-btn confirm" onClick={onConfirm}>确定</button></div>
      </div>
    </div>
  )
}

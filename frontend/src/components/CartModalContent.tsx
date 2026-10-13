import type { CartItem } from '@/types'
import { UiIcon } from './UiIcon'

type CartModalContentProps = {
  readonly cart: CartItem[]
  readonly onRemove: (index: number) => void
  readonly onUpdateQuantity: (index: number, delta: number) => void
  readonly total: number
}

export function CartModalContent({
  cart,
  onRemove,
  onUpdateQuantity,
  total,
}: CartModalContentProps): React.JSX.Element {
  return (
    <div>
      <div className="cart-list">
        {cart.map((item, index) => (
          <div key={`${item.offerId}-${index}`} className="cart-item">
            <div className="cart-item-info">
              <div className="cart-item-title">{item.name}</div>
              <div className="cart-item-price">
                ${item.price} x {item.quantity} = ${(item.price * item.quantity).toFixed(1)}
              </div>
            </div>
            <div className="cart-item-ctrl">
              <button
                type="button"
                className="cart-mini-btn"
                aria-label={`减少${item.name}数量`}
                onClick={() => onUpdateQuantity(index, -1)}
              >
                <UiIcon name="minus" size={16} />
              </button>
              <span style={{ fontWeight: 600, width: '20px', textAlign: 'center' }}>{item.quantity}</span>
              <button
                type="button"
                className="cart-mini-btn"
                aria-label={`增加${item.name}数量`}
                onClick={() => onUpdateQuantity(index, 1)}
              >
                <UiIcon name="plus" size={16} />
              </button>
              <button
                type="button"
                className="cart-mini-btn cart-remove"
                aria-label={`移除${item.name}`}
                onClick={() => onRemove(index)}
              >
                <UiIcon name="trash" size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>
      <div
        style={{
          marginTop: '15px',
          paddingTop: '15px',
          borderTop: '1px solid #eee',
          display: 'flex',
          justifyContent: 'space-between',
          fontWeight: 800,
          fontSize: '18px',
        }}
      >
        <span>总计</span>
        <span style={{ color: '#e53e3e' }}>${total.toFixed(1)}</span>
      </div>
    </div>
  )
}

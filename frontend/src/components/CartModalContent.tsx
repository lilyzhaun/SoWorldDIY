import type { CartItem } from '../types'

type CartModalContentProps = { readonly cart: CartItem[]; readonly onRemove: (index: number) => void; readonly onUpdateQuantity: (index: number, delta: number) => void; readonly total: number }

export function CartModalContent({ cart, onRemove, onUpdateQuantity, total }: CartModalContentProps): JSX.Element {
  return <div><div className="cart-list">{cart.map((item, index) => <div key={`${item.offerId}-${index}`} className="cart-item"><div className="cart-item-info"><div className="cart-item-title">{item.name}</div><div className="cart-item-price">${item.price} x {item.quantity} = ${(item.price * item.quantity).toFixed(1)}</div></div><div className="cart-item-ctrl"><button className="cart-mini-btn" onClick={() => onUpdateQuantity(index, -1)}>-</button><span style={{ fontWeight: 600, width: '20px', textAlign: 'center' }}>{item.quantity}</span><button className="cart-mini-btn" onClick={() => onUpdateQuantity(index, 1)}>+</button><button className="cart-mini-btn cart-remove" onClick={() => onRemove(index)}>×</button></div></div>)}</div><div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #eee', display: 'flex', justifyContent: 'space-between', fontWeight: 800, fontSize: '18px' }}><span>总计</span><span style={{ color: '#e53e3e' }}>${total.toFixed(1)}</span></div></div>
}

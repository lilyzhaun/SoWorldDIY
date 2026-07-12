type CartFabProps = { readonly count: number; readonly onOpen: () => void; readonly total: number }

export function CartFab({ count, onOpen, total }: CartFabProps): JSX.Element {
  return (
    <div id="cartFab" className="cart-fab" style={{ display: count > 0 ? 'flex' : 'none' }} onClick={onOpen}>
      <div className="cart-icon-wrapper"><svg className="icon"><use xlinkHref="#icon-cart"></use></svg><span id="cartCount" className="cart-badge">{count}</span></div>
      <span className="cart-total-preview" id="cartTotalPreview">${total.toFixed(1)}</span>
    </div>
  )
}

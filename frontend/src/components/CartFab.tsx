type CartFabProps = { readonly count: number; readonly onOpen: () => void; readonly total: number }

export function CartFab({ count, onOpen, total }: CartFabProps): JSX.Element {
  return (
    <button
      type="button"
      id="cartFab"
      className="cart-fab"
      style={{ display: count > 0 ? 'flex' : 'none' }}
      aria-label={`打开购物车，${count} 件商品，总计 $${total.toFixed(1)}`}
      onClick={onOpen}
    >
      <div className="cart-icon-wrapper">
        <svg className="icon">
          <use xlinkHref="#icon-cart"></use>
        </svg>
        <span id="cartCount" className="cart-badge">
          {count}
        </span>
      </div>
      <span className="cart-total-preview" id="cartTotalPreview">
        ${total.toFixed(1)}
      </span>
    </button>
  )
}

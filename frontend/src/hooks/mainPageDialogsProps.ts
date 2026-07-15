import type { CartQuantityDraft } from '@/hooks/usePurchaseCart'
import type { MainPageDialogs } from '@/components/MainPageDialogs'
import type { AvailableAccount, Subscription } from '@/types'

type DialogsProps = Parameters<typeof MainPageDialogs>[0]

type BuildDialogsInput = {
  readonly availableAccounts: AvailableAccount[]
  readonly balance: string
  readonly currentSubId: string
  readonly showFreePlans: boolean
  readonly subscriptions: Subscription[]
  readonly cart: DialogsProps['cart']['cart']
  readonly cartCount: number
  readonly cartTotal: number
  readonly purchaseDraft: DialogsProps['actions']['purchaseDraft']
  readonly transferSubmitting: boolean
  readonly removeCartItem: DialogsProps['cart']['onRemoveCartItem']
  readonly updateCartItem: DialogsProps['cart']['onUpdateCartItem']
  readonly setPurchaseDraft: DialogsProps['purchase']['onChangePurchaseDraft']
  readonly setCartQtyDraft: (draft: CartQuantityDraft | null) => void
  readonly confirmAddToCart: () => void
  readonly openCartModal: (count: number) => void
  readonly onCheckout: () => void
  readonly onConfirmPurchase: () => void
  readonly onConfirmTransfer: () => void
  readonly frame: DialogsProps['frame']
  readonly inbox: DialogsProps['inbox']
  readonly history: DialogsProps['history']
  readonly quantityPresence: DialogsProps['quantity']['presence']
  readonly transfer: DialogsProps['transfer']
  readonly onSwitchSubscription: (sub: Subscription) => void
  readonly closeCustomModal: () => void
}

export function buildMainPageDialogs(input: BuildDialogsInput): DialogsProps {
  return {
    accountSwitch: {
      availableAccounts: input.availableAccounts,
      currentSubId: input.currentSubId,
      onAddAccount: () => {
        window.location.href = '/?add=1'
      },
      onSwitchAccount: (identifier: string) => {
        window.location.href = `/main/${identifier}`
      },
      onSwitchSubscription: input.onSwitchSubscription,
      subscriptions: input.subscriptions,
    },
    actions: {
      onCheckout: input.onCheckout,
      onConfirmPurchase: input.onConfirmPurchase,
      onConfirmTransfer: input.onConfirmTransfer,
      purchaseDraft: input.purchaseDraft,
      transferSubmitting: input.transferSubmitting,
    },
    cart: {
      cart: input.cart,
      onRemoveCartItem: input.removeCartItem,
      onUpdateCartItem: input.updateCartItem,
      total: input.cartTotal,
    },
    cartFab: {
      count: input.cartCount,
      onOpen: () => input.openCartModal(input.cart.length),
      total: input.cartTotal,
    },
    frame: input.frame,
    inbox: input.inbox,
    history: input.history,
    purchase: {
      balance: input.balance,
      onChangePurchaseDraft: input.setPurchaseDraft,
      purchaseDraft: input.purchaseDraft,
      showFreePlans: input.showFreePlans,
    },
    quantity: {
      cart: input.cart,
      onCancel: () => input.setCartQtyDraft(null),
      onConfirm: input.confirmAddToCart,
      onUpdateDraft: input.setCartQtyDraft,
      presence: input.quantityPresence,
    },
    transfer: input.transfer,
  }
}

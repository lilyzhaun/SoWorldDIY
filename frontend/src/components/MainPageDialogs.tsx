import type { Dispatch, SetStateAction } from 'react'

import type { AlertState, ModalKind } from '@/hooks/useAppModal'
import type { PresenceValue } from '@/hooks/usePresenceValue'
import type { CartQuantityDraft, PurchaseDraft } from '@/hooks/usePurchaseCart'
import type {
  AvailableAccount,
  CartItem,
  HistoryItem,
  InboxMessage,
  ModalMode,
  Subscription,
  TransferDraft,
} from '@/types'
import { AccountSwitchModalContent } from './AccountSwitchModalContent'
import { CartFab } from './CartFab'
import { CartModalContent } from './CartModalContent'
import { CartQuantityModal } from './CartQuantityModal'
import { CustomModal } from './CustomModal'
import { HistoryModal } from './HistoryModal'
import { InboxModal } from './InboxModal'
import { MainModalActions } from './MainModalActions'
import { PurchaseModalContent } from './PurchaseModalContent'
import { StatusMessage } from './StatusMessage'
import { TransferModalContent } from './TransferModalContent'

type CartFabContent = { readonly count: number; readonly onOpen: () => void; readonly total: number }

type InboxContent = {
  readonly activeInboxIndex: number | null
  readonly inboxLoading: boolean
  readonly inboxMessages: InboxMessage[]
  readonly inboxOpen: boolean
  readonly onClose: () => void
  readonly onRefresh: () => void
  readonly onSelectMessage: (index: number | null) => void
  readonly subscriptions: Subscription[]
}

type HistoryContent = {
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

type ModalFrameContent = {
  readonly alert: AlertState
  readonly modalKind: ModalKind
  readonly modalMode: ModalMode
  readonly modalTitle: string
  readonly onClose: () => void
  readonly open: boolean
}

type ModalActionsContent = {
  readonly onConfirmPurchase: () => void
  readonly onConfirmTransfer: () => void
  readonly onCheckout: () => void
  readonly purchaseDraft: PurchaseDraft | null
  readonly transferSubmitting: boolean
}

type AccountSwitchContent = {
  readonly availableAccounts: AvailableAccount[]
  readonly currentSubId: string
  readonly onAddAccount: () => void
  readonly onSwitchAccount: (identifier: string) => void
  readonly onSwitchSubscription: (subscription: Subscription) => void
  readonly subscriptions: Subscription[]
}

type CartContent = {
  readonly cart: CartItem[]
  readonly onRemoveCartItem: (index: number) => void
  readonly onUpdateCartItem: (index: number, delta: number) => void
  readonly total: number
}

type PurchaseContent = {
  readonly balance: string
  readonly onChangePurchaseDraft: Dispatch<SetStateAction<PurchaseDraft | null>>
  readonly purchaseDraft: PurchaseDraft | null
  readonly showFreePlans: boolean
}

type TransferContent = {
  readonly onChangeTransferAmount: (amount: string) => void
  readonly onChangeTransferTarget: (target: string) => void
  readonly transferAmount: string
  readonly transferDraft: TransferDraft | null
  readonly transferError: string
  readonly transferTarget: string
}

type QuantityContent = {
  readonly cart: CartItem[]
  readonly onCancel: () => void
  readonly onConfirm: () => void
  readonly onUpdateDraft: (draft: CartQuantityDraft) => void
  readonly presence: PresenceValue<CartQuantityDraft>
}

type MainPageDialogsProps = {
  readonly accountSwitch: AccountSwitchContent
  readonly actions: ModalActionsContent
  readonly cart: CartContent
  readonly cartFab: CartFabContent
  readonly frame: ModalFrameContent
  readonly history: HistoryContent
  readonly inbox: InboxContent
  readonly purchase: PurchaseContent
  readonly quantity: QuantityContent
  readonly transfer: TransferContent
}

export function MainPageDialogs({
  accountSwitch,
  actions,
  cart,
  cartFab,
  frame,
  history,
  inbox,
  purchase,
  quantity,
  transfer,
}: MainPageDialogsProps): JSX.Element {
  return (
    <>
      <CartFab {...cartFab} />

      <InboxModal {...inbox} />

      <HistoryModal {...history} />

      <CustomModal
        actions={
          <MainModalActions
            modalKind={frame.modalKind}
            purchaseDraft={actions.purchaseDraft}
            transferSubmitting={actions.transferSubmitting}
            onClose={frame.onClose}
            onCheckout={actions.onCheckout}
            onConfirmPurchase={actions.onConfirmPurchase}
            onConfirmTransfer={actions.onConfirmTransfer}
          />
        }
        mode={frame.modalMode}
        onClose={frame.onClose}
        open={frame.open}
        title={frame.modalTitle}
      >
        {frame.modalKind === 'alert' ? (
          frame.alert.tone ? (
            <StatusMessage message={frame.alert.text} tone={frame.alert.tone} />
          ) : (
            frame.alert.text
          )
        ) : null}
        {frame.modalKind === 'switch' ? (
          <AccountSwitchModalContent
            availableAccounts={accountSwitch.availableAccounts}
            currentSubId={accountSwitch.currentSubId}
            onAddAccount={accountSwitch.onAddAccount}
            onSwitchAccount={accountSwitch.onSwitchAccount}
            onSwitchSubscription={accountSwitch.onSwitchSubscription}
            subscriptions={accountSwitch.subscriptions}
          />
        ) : null}
        {frame.modalKind === 'cart' ? (
          <CartModalContent
            cart={cart.cart}
            onRemove={cart.onRemoveCartItem}
            onUpdateQuantity={cart.onUpdateCartItem}
            total={cart.total}
          />
        ) : null}
        {frame.modalKind === 'purchase' && purchase.purchaseDraft ? (
          <PurchaseModalContent
            balance={purchase.balance}
            draft={purchase.purchaseDraft}
            onChangeDraft={purchase.onChangePurchaseDraft}
            showNewLineOption={purchase.showFreePlans && purchase.purchaseDraft.source === 'cart'}
          />
        ) : null}
        {frame.modalKind === 'transfer' && transfer.transferDraft ? (
          <TransferModalContent
            amount={transfer.transferAmount}
            draft={transfer.transferDraft}
            error={transfer.transferError}
            onChangeAmount={transfer.onChangeTransferAmount}
            onChangeTarget={transfer.onChangeTransferTarget}
            target={transfer.transferTarget}
          />
        ) : null}
      </CustomModal>

      {quantity.presence.value !== null ? (
        <CartQuantityModal
          cart={quantity.cart}
          draft={quantity.presence.value}
          onCancel={quantity.onCancel}
          onConfirm={quantity.onConfirm}
          onExitComplete={quantity.presence.completeExit}
          onUpdateDraft={quantity.onUpdateDraft}
          phase={quantity.presence.phase}
        />
      ) : null}
    </>
  )
}

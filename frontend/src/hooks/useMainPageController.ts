import { useMemo, useState } from 'react'

import { BUILD_VERSION } from '@/build'
import { useAppModal } from '@/hooks/useAppModal'
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock'
import { useCmn } from '@/hooks/useCmn'
import { useHistory } from '@/hooks/useHistory'
import { useInbox } from '@/hooks/useInbox'
import { useLogout } from '@/hooks/useLogout'
import { usePresenceValue } from '@/hooks/usePresenceValue'
import { useProfileBootstrap } from '@/hooks/useProfileBootstrap'
import { useProfileRefresh } from '@/hooks/useProfileRefresh'
import { usePurchaseCart } from '@/hooks/usePurchaseCart'
import { useServiceWorker } from '@/hooks/useServiceWorker'
import { useSubscriptionBootstrap } from '@/hooks/useSubscriptionBootstrap'
import { useTransfer } from '@/hooks/useTransfer'
import type { AvailableAccount, Category, Plan, Subscription } from '@/types'
import { getAccountIdFromPathname } from '@/utils/mainPage'
import { filterPlansForCategory } from '@/utils/filterPlans'
import { nextAllTabState } from '@/utils/switchCategory'
import type { MainPageView } from '@/components/MainPageView'
import { buildMainPageDialogs } from '@/hooks/mainPageDialogsProps'

type ViewProps = Parameters<typeof MainPageView>[0]

export function useMainPageController(): ViewProps {
  const accountId = getAccountIdFromPathname(window.location.pathname)
  const [loading, setLoading] = useState(true)
  const [noNumberMode, setNoNumberMode] = useState(false)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<Category>('ALL')
  const [allTabClickCount, setAllTabClickCount] = useState(0)
  const [showFreePlans, setShowFreePlans] = useState(false)
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [availableAccounts, setAvailableAccounts] = useState<AvailableAccount[]>([])
  const [currentSubId, setCurrentSubId] = useState('')
  const [balance, setBalance] = useState('0.0')
  const [plans, setPlans] = useState<Plan[]>([])
  const [plansLoading, setPlansLoading] = useState(true)
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)

  const purchase = usePurchaseCart(accountId, currentSubId, balance)
  const loaderPresence = usePresenceValue(loading ? true : null)
  const cartQtyPresence = usePresenceValue(purchase.cartQtyDraft)
  const inbox = useInbox(accountId)
  const history = useHistory(accountId, currentSubId)
  const transfer = useTransfer(accountId, currentSubId)
  const modal = useAppModal({ onAfterClose: transfer.resetTransfer })
  const cmn = useCmn(accountId, currentSubId, category === 'CMN')
  const profileRefresh = useProfileRefresh({
    accountId,
    setAvailableAccounts,
    setSubscriptions,
    showAlert: modal.showAlert,
  })

  const currentSub = useMemo(
    () => subscriptions.find((item) => item.subscriptionId === currentSubId) ?? null,
    [subscriptions, currentSubId],
  )

  const filteredPlans = useMemo(
    () => filterPlansForCategory(plans, search, category, showFreePlans),
    [plans, search, category, showFreePlans],
  )

  useServiceWorker(BUILD_VERSION)
  useBodyScrollLock(inbox.inboxOpen || history.historyOpen || modal.showModal || purchase.cartQtyDraft !== null)

  useProfileBootstrap({
    accountId,
    currentSubId,
    setAvailableAccounts,
    setCurrentSubId,
    setLoading,
    setNoNumberMode,
    setSubscriptions,
  })

  useSubscriptionBootstrap(
    {
      accountId,
      category,
      currentSubId,
      noNumberMode,
      setBalance,
      setPlans,
      setPlansLoading,
    },
    {
      checkCmnEligibility: cmn.checkCmnEligibility,
      fetchInbox: inbox.fetchInbox,
      fetchHistory: history.fetchHistory,
      resetCart: purchase.resetCart,
      resetHistory: history.resetHistory,
      showAlert: modal.showAlert,
    },
  )

  const handleLogout = useLogout(accountId, modal.showAlert)

  const switchCategory = (nextCategory: Category): void => {
    if (nextCategory === 'ALL') {
      const next = nextAllTabState({ allTabClickCount, showFreePlans })
      setAllTabClickCount(next.allTabClickCount)
      setShowFreePlans(next.showFreePlans)
      if (next.revealFreePlans) modal.showAlert('免费套餐已显示')
    } else {
      setAllTabClickCount(0)
    }
    setCategory(nextCategory)
    if (nextCategory === 'CMN' && !cmn.cmnData) void cmn.checkCmnEligibility()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const showPurchaseModal = (title: string, price: number, source: 'cart' | 'cmn'): void => {
    purchase.openPurchaseModal(title, price, source, () => modal.openKind('purchase', '确认订单', 'center'))
  }

  const handleSubmitTransfer = async (): Promise<void> => {
    const target = await transfer.submitTransfer(currentSub)
    if (!target) return
    modal.closeCustomModal()
    modal.showAlert(`资源已成功转移给 ${target}`, '办理成功', 'success')
    void profileRefresh.refreshProfileData()
  }

  return {
    accountId,
    loaderPresence,
    header: {
      availableAccounts,
      balance,
      category,
      currentSub,
      noNumberMode,
      onLogout: handleLogout,
      onOpenHistory: () => void history.openHistory(modal.showAlert),
      onOpenInbox: () => void inbox.openInbox(modal.showAlert),
      onOpenSwitch: modal.openSwitchModal,
      onSearchChange: setSearch,
      onShowAlert: modal.showAlert,
      onSwitchCategory: switchCategory,
      search,
    },
    content: {
      plans: {
        filteredPlans,
        noNumberMode,
        onAddToCart: purchase.openAddToCart,
        onSelectPlan: setSelectedPlanId,
        plansLoading,
        selectedPlanId,
        showFreePlans,
        visible: category !== 'SUBSCRIBED' && category !== 'CMN',
      },
      offers: {
        currentSub,
        onOpenTransfer: (event, draft) =>
          transfer.openTransferModal(event, draft, () => {
            modal.openKind('transfer', '资源转移', 'center')
          }),
        onRefresh: () => void profileRefresh.refreshProfileData(),
        onSelectOffer: setSelectedPlanId,
        refreshingUsage: profileRefresh.refreshingUsage,
        selectedPlanId,
        visible: category === 'SUBSCRIBED',
      },
      cmn: {
        autoRefresh: cmn.cmnAutoRefresh,
        canRefresh: cmn.cmnCanRefresh,
        cooldown: cmn.cmnCooldown,
        data: cmn.cmnData,
        error: cmn.cmnError,
        loading: cmn.cmnLoading,
        numbers: cmn.cmnNumbers,
        numbersLoading: cmn.cmnNumbersLoading,
        numbersMode: cmn.cmnNumbersMode,
        onAutoRefreshCancel: cmn.cancelCmnAutoRefresh,
        onAutoRefreshStart: () => cmn.startCmnAutoRefresh(modal.showAlert),
        onPatternChange: cmn.changeCmnPattern,
        onRefresh: () => void cmn.refreshCmnNumbers(modal.showAlert),
        onSelectNumber: cmn.setSelectedNumber,
        onSubmit: () => cmn.submitChangeNumber(modal.showAlert, showPurchaseModal),
        parsedPattern: cmn.parsedCmnPattern,
        pattern: cmn.cmnPattern,
        selectedNumber: cmn.selectedNumber,
        visible: category === 'CMN',
      },
      footerVisible: category === 'ALL' || category === 'CMN',
    },
    dialogs: buildMainPageDialogs({
      availableAccounts,
      balance,
      currentSubId,
      showFreePlans,
      subscriptions,
      cart: purchase.cart,
      cartCount: purchase.cartCount,
      cartTotal: purchase.cartTotal,
      purchaseDraft: purchase.purchaseDraft,
      transferSubmitting: transfer.transferSubmitting,
      removeCartItem: purchase.removeCartItem,
      updateCartItem: purchase.updateCartItem,
      setPurchaseDraft: purchase.setPurchaseDraft,
      setCartQtyDraft: purchase.setCartQtyDraft,
      confirmAddToCart: () => purchase.confirmAddToCart(modal.showAlert),
      openCartModal: modal.openCartModal,
      onCheckout: () => showPurchaseModal(`购物车共 ${purchase.cart.length} 项商品`, purchase.cartTotal, 'cart'),
      onConfirmPurchase: () => {
        if (!purchase.purchaseDraft) return
        if (purchase.purchaseDraft.source === 'cart') void purchase.submitCheckout(modal.showAlert)
        else void purchase.submitCmnPurchase(cmn.cmnData, cmn.selectedNumber, modal.showAlert)
      },
      onConfirmTransfer: () => void handleSubmitTransfer(),
      frame: {
        alert: modal.alert,
        modalKind: modal.modalKind,
        modalMode: modal.modalMode,
        modalTitle: modal.modalTitle,
        onClose: modal.closeCustomModal,
        open: modal.showModal,
      },
      inbox: {
        activeInboxIndex: inbox.activeInboxIndex,
        inboxLoading: inbox.inboxLoading,
        inboxMessages: inbox.inboxMessages,
        inboxOpen: inbox.inboxOpen,
        onClose: () => inbox.setInboxOpen(false),
        onRefresh: () => void inbox.fetchInbox(true, modal.showAlert),
        onSelectMessage: inbox.setActiveInboxIndex,
        subscriptions,
      },
      history: {
        histEnd: history.histEnd,
        histStart: history.histStart,
        historyDetailIndex: history.historyDetailIndex,
        historyItems: history.historyItems,
        historyLoading: history.historyLoading,
        historyOpen: history.historyOpen,
        onChangeEnd: history.setHistEnd,
        onChangeStart: history.setHistStart,
        onClose: () => history.setHistoryOpen(false),
        onQuery: () => void history.fetchHistory(true, false, modal.showAlert),
        onSelectDetail: history.setHistoryDetailIndex,
      },
      quantityPresence: cartQtyPresence,
      transfer: {
        onChangeTransferAmount: transfer.setTransferAmount,
        onChangeTransferTarget: transfer.setTransferTarget,
        transferAmount: transfer.transferAmount,
        transferDraft: transfer.transferDraft,
        transferError: transfer.transferError,
        transferTarget: transfer.transferTarget,
      },
      onSwitchSubscription: (sub: Subscription) => {
        if (sub.subscriptionId !== currentSubId) setCurrentSubId(sub.subscriptionId)
        modal.closeCustomModal()
      },
      closeCustomModal: modal.closeCustomModal,
    }),
  }
}

import { useMemo, useState } from 'react'

import { BUILD_VERSION } from '@/build'
import { MainHeader } from '@/components/MainHeader'
import { MainPageContent } from '@/components/MainPageContent'
import { MainPageDialogs } from '@/components/MainPageDialogs'
import { useAppModal } from '@/hooks/useAppModal'
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock'
import { useCmn } from '@/hooks/useCmn'
import { useHistory } from '@/hooks/useHistory'
import { useInbox } from '@/hooks/useInbox'
import { isRootOpacityTransition, usePresenceValue } from '@/hooks/usePresenceValue'
import { useProfileBootstrap } from '@/hooks/useProfileBootstrap'
import { useProfileRefresh } from '@/hooks/useProfileRefresh'
import { usePurchaseCart } from '@/hooks/usePurchaseCart'
import { useServiceWorker } from '@/hooks/useServiceWorker'
import { useSubscriptionBootstrap } from '@/hooks/useSubscriptionBootstrap'
import { useTransfer } from '@/hooks/useTransfer'
import type { AvailableAccount, Category, Plan, Subscription } from '@/types'
import { getAccountIdFromPathname } from '@/utils/mainPage'
import { SVG_SPRITE } from '@/assets/svgSprite'

export function MainPage(): JSX.Element {
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

  const {
    cart,
    cartCount,
    cartQtyDraft,
    cartTotal,
    confirmAddToCart,
    openAddToCart,
    openPurchaseModal,
    purchaseDraft,
    removeCartItem,
    resetCart,
    setCartQtyDraft,
    setPurchaseDraft,
    submitCheckout,
    submitCmnPurchase,
    updateCartItem,
  } = usePurchaseCart(accountId, currentSubId, balance)
  const loaderPresence = usePresenceValue(loading ? true : null)
  const cartQtyPresence = usePresenceValue(cartQtyDraft)

  const {
    activeInboxIndex,
    fetchInbox,
    inboxLoading,
    inboxMessages,
    inboxOpen,
    openInbox,
    setActiveInboxIndex,
    setInboxOpen,
  } = useInbox(accountId)

  const {
    fetchHistory,
    histEnd,
    histStart,
    historyDetailIndex,
    historyItems,
    historyLoading,
    historyOpen,
    openHistory,
    resetHistory,
    setHistEnd,
    setHistStart,
    setHistoryDetailIndex,
    setHistoryOpen,
  } = useHistory(accountId, currentSubId)

  const {
    openTransferModal,
    resetTransfer,
    setTransferAmount,
    setTransferTarget,
    submitTransfer,
    transferAmount,
    transferDraft,
    transferError,
    transferSubmitting,
    transferTarget,
  } = useTransfer(accountId, currentSubId)

  const {
    alert,
    closeCustomModal,
    modalKind,
    modalMode,
    modalTitle,
    openCartModal,
    openKind,
    openSwitchModal,
    showAlert,
    showModal,
  } = useAppModal({
    onAfterClose: resetTransfer,
  })

  const {
    cancelCmnAutoRefresh,
    changeCmnPattern,
    checkCmnEligibility,
    cmnAutoRefresh,
    cmnCanRefresh,
    cmnCooldown,
    cmnData,
    cmnError,
    cmnLoading,
    cmnNumbers,
    cmnNumbersLoading,
    cmnPattern,
    parsedCmnPattern,
    refreshCmnNumbers,
    selectedNumber,
    setSelectedNumber,
    startCmnAutoRefresh,
    submitChangeNumber,
  } = useCmn(accountId, currentSubId, category === 'CMN')
  const { refreshingUsage, refreshProfileData } = useProfileRefresh({
    accountId,
    setAvailableAccounts,
    setSubscriptions,
    showAlert,
  })

  const currentSub = useMemo(
    () => subscriptions.find((item) => item.subscriptionId === currentSubId) ?? null,
    [subscriptions, currentSubId],
  )

  const filteredPlans = useMemo(() => {
    const keyword = search.toLowerCase().trim()
    return plans.filter((plan) => {
      if (category === 'CMN' || category === 'SUBSCRIBED') return false
      if (plan.price <= 0 && !showFreePlans) return false
      if (category === 'OTHER' && plan.category !== 'VOICE' && plan.category !== 'OTHER') return false
      if (category !== 'ALL' && category !== 'OTHER' && plan.category !== category) return false
      if (!keyword) return true
      return `${plan.name}${plan.desc}${plan.price}`.toLowerCase().includes(keyword)
    })
  }, [plans, search, category, showFreePlans])

  useServiceWorker(BUILD_VERSION)
  useBodyScrollLock(inboxOpen || historyOpen || showModal || cartQtyDraft !== null)

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
      checkCmnEligibility,
      fetchInbox,
      fetchHistory,
      resetCart,
      resetHistory,
      showAlert,
    },
  )

  const switchCategory = (nextCategory: Category): void => {
    if (nextCategory === 'ALL') {
      const nextCount = allTabClickCount + 1
      if (nextCount >= 5 && !showFreePlans) {
        setShowFreePlans(true)
        setAllTabClickCount(0)
        showAlert('免费套餐已显示')
      } else {
        setAllTabClickCount(nextCount)
      }
    } else {
      setAllTabClickCount(0)
    }
    setCategory(nextCategory)
    if (nextCategory === 'CMN' && !cmnData) void checkCmnEligibility()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleOpenCartModal = (): void => {
    openCartModal(cart.length)
  }

  const showPurchaseModal = (title: string, price: number, source: 'cart' | 'cmn'): void => {
    openPurchaseModal(title, price, source, () => {
      openKind('purchase', '确认订单', 'center')
    })
  }

  const handleSubmitTransfer = async (): Promise<void> => {
    const target = await submitTransfer(currentSub)
    if (!target) return
    closeCustomModal()
    showAlert(`资源已成功转移给 ${target}`, '办理成功', 'success')
    void refreshProfileData()
  }

  const performSwitch = (sub: Subscription): void => {
    if (sub.subscriptionId !== currentSubId) setCurrentSubId(sub.subscriptionId)
    closeCustomModal()
  }

  const switchAccount = (identifier: string): void => {
    window.location.href = `/main/${identifier}`
  }

  const addAccount = (): void => {
    window.location.href = '/?add=1'
  }

  const handleLogout = (): void => {
    let url = '/logout'
    if (accountId) url += `?account_id=${accountId}`
    window.location.href = url
  }

  return (
    <>
      <div style={{ display: 'none' }} dangerouslySetInnerHTML={{ __html: SVG_SPRITE }} />
      <input type="hidden" id="current-account-id-ref" defaultValue={accountId} />
      {loaderPresence.value !== null ? (
        <div
          id="global-loader"
          className={`global-loader ${loaderPresence.phase}`}
          onTransitionEnd={(event) => {
            if (isRootOpacityTransition(event)) loaderPresence.completeExit()
          }}
        >
          <div className="loader-content">
            <div className="spinner"></div>
            <div className="loader-text">正在同步账户信息…</div>
          </div>
        </div>
      ) : null}

      <MainHeader
        availableAccounts={availableAccounts}
        balance={balance}
        category={category}
        currentSub={currentSub}
        noNumberMode={noNumberMode}
        onLogout={handleLogout}
        onOpenHistory={() => void openHistory(showAlert)}
        onOpenInbox={() => void openInbox(showAlert)}
        onOpenSwitch={openSwitchModal}
        onSearchChange={setSearch}
        onShowAlert={showAlert}
        onSwitchCategory={switchCategory}
        search={search}
      />

      <MainPageContent
        plans={{
          filteredPlans,
          noNumberMode,
          onAddToCart: openAddToCart,
          onSelectPlan: setSelectedPlanId,
          plansLoading,
          selectedPlanId,
          showFreePlans,
          visible: category !== 'SUBSCRIBED' && category !== 'CMN',
        }}
        offers={{
          currentSub,
          onOpenTransfer: (event, draft) =>
            openTransferModal(event, draft, () => {
              openKind('transfer', '资源转移', 'center')
            }),
          onRefresh: () => void refreshProfileData(),
          onSelectOffer: setSelectedPlanId,
          refreshingUsage,
          selectedPlanId,
          visible: category === 'SUBSCRIBED',
        }}
        cmn={{
          autoRefresh: cmnAutoRefresh,
          canRefresh: cmnCanRefresh,
          cooldown: cmnCooldown,
          data: cmnData,
          error: cmnError,
          loading: cmnLoading,
          numbers: cmnNumbers,
          numbersLoading: cmnNumbersLoading,
          onAutoRefreshCancel: cancelCmnAutoRefresh,
          onAutoRefreshStart: () => startCmnAutoRefresh(showAlert),
          onPatternChange: changeCmnPattern,
          onRefresh: () => void refreshCmnNumbers(showAlert),
          onSelectNumber: setSelectedNumber,
          onSubmit: () => submitChangeNumber(showAlert, showPurchaseModal),
          parsedPattern: parsedCmnPattern,
          pattern: cmnPattern,
          selectedNumber,
          visible: category === 'CMN',
        }}
        footerVisible={category === 'ALL' || category === 'CMN'}
      />

      <MainPageDialogs
        accountSwitch={{
          availableAccounts,
          currentSubId,
          onAddAccount: addAccount,
          onSwitchAccount: switchAccount,
          onSwitchSubscription: performSwitch,
          subscriptions,
        }}
        actions={{
          onCheckout: () => showPurchaseModal(`购物车共 ${cart.length} 项商品`, cartTotal, 'cart'),
          onConfirmPurchase: () => {
            if (!purchaseDraft) return
            if (purchaseDraft.source === 'cart') void submitCheckout(showAlert)
            else void submitCmnPurchase(cmnData, selectedNumber, showAlert)
          },
          onConfirmTransfer: () => void handleSubmitTransfer(),
          purchaseDraft,
          transferSubmitting,
        }}
        cart={{ cart, onRemoveCartItem: removeCartItem, onUpdateCartItem: updateCartItem, total: cartTotal }}
        cartFab={{ count: cartCount, onOpen: handleOpenCartModal, total: cartTotal }}
        frame={{ alert, modalKind, modalMode, modalTitle, onClose: closeCustomModal, open: showModal }}
        inbox={{
          activeInboxIndex,
          inboxLoading,
          inboxMessages,
          inboxOpen,
          onClose: () => setInboxOpen(false),
          onRefresh: () => void fetchInbox(true, showAlert),
          onSelectMessage: setActiveInboxIndex,
          subscriptions,
        }}
        history={{
          histEnd,
          histStart,
          historyDetailIndex,
          historyItems,
          historyLoading,
          historyOpen,
          onChangeEnd: setHistEnd,
          onChangeStart: setHistStart,
          onClose: () => setHistoryOpen(false),
          onQuery: () => void fetchHistory(true, false, showAlert),
          onSelectDetail: setHistoryDetailIndex,
        }}
        purchase={{ balance, onChangePurchaseDraft: setPurchaseDraft, purchaseDraft, showFreePlans }}
        quantity={{
          cart,
          onCancel: () => setCartQtyDraft(null),
          onConfirm: () => confirmAddToCart(showAlert),
          onUpdateDraft: setCartQtyDraft,
          presence: cartQtyPresence,
        }}
        transfer={{
          onChangeTransferAmount: setTransferAmount,
          onChangeTransferTarget: setTransferTarget,
          transferAmount,
          transferDraft,
          transferError,
          transferTarget,
        }}
      />
    </>
  )
}

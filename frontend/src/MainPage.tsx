import { useMemo, useState } from 'react'

import { apiGet } from '@/api/client'
import { BUILD_VERSION } from '@/build'
import { AccountSwitchModalContent } from '@/components/AccountSwitchModalContent'
import { ActiveOffersSection } from '@/components/ActiveOffersSection'
import { CartFab } from '@/components/CartFab'
import { CartModalContent } from '@/components/CartModalContent'
import { CartQuantityModal } from '@/components/CartQuantityModal'
import { CmnSection } from '@/components/CmnSection'
import { CustomModal } from '@/components/CustomModal'
import { HistoryModal } from '@/components/HistoryModal'
import { InboxModal } from '@/components/InboxModal'
import { MainFooter } from '@/components/MainFooter'
import { MainHeader } from '@/components/MainHeader'
import { MainModalActions } from '@/components/MainModalActions'
import { PlanList } from '@/components/PlanList'
import { PurchaseModalContent } from '@/components/PurchaseModalContent'
import { StatusMessage } from '@/components/StatusMessage'
import { TransferModalContent } from '@/components/TransferModalContent'
import { useAppModal } from '@/hooks/useAppModal'
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock'
import { useCmn } from '@/hooks/useCmn'
import { useHistory } from '@/hooks/useHistory'
import { useInbox } from '@/hooks/useInbox'
import { isRootOpacityTransition, usePresenceValue } from '@/hooks/usePresenceValue'
import { useProfileBootstrap } from '@/hooks/useProfileBootstrap'
import { usePurchaseCart } from '@/hooks/usePurchaseCart'
import { useServiceWorker } from '@/hooks/useServiceWorker'
import { useSubscriptionBootstrap } from '@/hooks/useSubscriptionBootstrap'
import { useTransfer } from '@/hooks/useTransfer'
import type { AvailableAccount, Category, Plan, ProfileResponse, Subscription } from '@/types'
import { getAccountIdFromPathname, getApiUrl } from '@/utils/mainPage'
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

  const { cart, cartCount, cartQtyDraft, cartTotal, confirmAddToCart, openAddToCart, openPurchaseModal, purchaseDraft, removeCartItem, resetCart, setCartQtyDraft, setPurchaseDraft, submitCheckout, submitCmnPurchase, updateCartItem } = usePurchaseCart(accountId, currentSubId, balance)
  const loaderPresence = usePresenceValue(loading ? true : null)
  const cartQtyPresence = usePresenceValue(cartQtyDraft)

  const { activeInboxIndex, fetchInbox, inboxLoading, inboxMessages, inboxOpen, openInbox, setActiveInboxIndex, setInboxOpen } = useInbox(accountId)

  const { fetchHistory, histEnd, histStart, historyDetailIndex, historyItems, historyLoading, historyOpen, openHistory, resetHistory, setHistEnd, setHistStart, setHistoryDetailIndex, setHistoryOpen } = useHistory(accountId, currentSubId)

  const { openTransferModal, resetTransfer, setTransferAmount, setTransferTarget, submitTransfer, transferAmount, transferDraft, transferError, transferSubmitting, transferTarget } = useTransfer(accountId, currentSubId)

  const { alert, closeCustomModal, modalKind, modalMode, modalTitle, openCartModal, openKind, openSwitchModal, showAlert, showModal } = useAppModal({
    onAfterClose: resetTransfer,
  })

  const [refreshingUsage, setRefreshingUsage] = useState(false)

  const { cancelCmnAutoRefresh, changeCmnPattern, checkCmnEligibility, cmnAutoRefresh, cmnCanRefresh, cmnCooldown, cmnData, cmnError, cmnLoading, cmnNumbers, cmnNumbersLoading, cmnPattern, parsedCmnPattern, refreshCmnNumbers, selectedNumber, setSelectedNumber, startCmnAutoRefresh, submitChangeNumber } = useCmn(accountId, currentSubId, category === 'CMN')

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

  useProfileBootstrap({ accountId, currentSubId, setAvailableAccounts, setCurrentSubId, setLoading, setNoNumberMode, setSubscriptions })

  useSubscriptionBootstrap({
    accountId,
    category,
    currentSubId,
    noNumberMode,
    setBalance,
    setPlans,
    setPlansLoading,
  }, {
    checkCmnEligibility,
    fetchInbox,
    fetchHistory,
    resetCart,
    resetHistory,
    showAlert,
  })

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

  const refreshProfileData = async (): Promise<void> => {
    setRefreshingUsage(true)
    try {
      const url = getApiUrl(`/api/profile?refresh=true&_t=${Date.now()}`, accountId)
      const d = await apiGet<ProfileResponse>(url)
      if (d.status === 'success') {
        const nextSubs = d.data.subscriptions || []
        setSubscriptions(nextSubs)
        setAvailableAccounts(d.data.available_accounts || [])
      } else {
        showAlert('刷新失败')
      }
    } catch {
      showAlert('网络连接失败')
    } finally {
      window.setTimeout(() => setRefreshingUsage(false), 500)
    }
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
          <div className="loader-content"><div className="spinner"></div><div className="loader-text">正在同步账户信息…</div></div>
        </div>
      ) : null}

      <MainHeader availableAccounts={availableAccounts} balance={balance} category={category} currentSub={currentSub} noNumberMode={noNumberMode} onLogout={handleLogout} onOpenHistory={() => void openHistory(showAlert)} onOpenInbox={() => void openInbox(showAlert)} onOpenSwitch={openSwitchModal} onSearchChange={setSearch} onShowAlert={showAlert} onSwitchCategory={switchCategory} search={search} />

      <div className="content-wrapper">
        <PlanList filteredPlans={filteredPlans} noNumberMode={noNumberMode} onAddToCart={openAddToCart} onSelectPlan={setSelectedPlanId} plansLoading={plansLoading} selectedPlanId={selectedPlanId} showFreePlans={showFreePlans} visible={category !== 'SUBSCRIBED' && category !== 'CMN'} />

        <ActiveOffersSection currentSub={currentSub} onOpenTransfer={(event, draft) => openTransferModal(event, draft, () => { openKind('transfer', '资源转移', 'center') })} onRefresh={() => void refreshProfileData()} onSelectOffer={setSelectedPlanId} refreshingUsage={refreshingUsage} selectedPlanId={selectedPlanId} visible={category === 'SUBSCRIBED'} />
        <CmnSection autoRefresh={cmnAutoRefresh} canRefresh={cmnCanRefresh} cooldown={cmnCooldown} data={cmnData} error={cmnError} loading={cmnLoading} numbers={cmnNumbers} numbersLoading={cmnNumbersLoading} onAutoRefreshCancel={cancelCmnAutoRefresh} onAutoRefreshStart={() => startCmnAutoRefresh(showAlert)} onPatternChange={changeCmnPattern} onRefresh={() => void refreshCmnNumbers(showAlert)} onSelectNumber={setSelectedNumber} onSubmit={() => submitChangeNumber(showAlert, showPurchaseModal)} parsedPattern={parsedCmnPattern} pattern={cmnPattern} selectedNumber={selectedNumber} visible={category === 'CMN'} />
        <MainFooter visible={category === 'ALL' || category === 'CMN'} />
      </div>

      <CartFab count={cartCount} onOpen={handleOpenCartModal} total={cartTotal} />

      <InboxModal
        activeInboxIndex={activeInboxIndex}
        inboxLoading={inboxLoading}
        inboxMessages={inboxMessages}
        inboxOpen={inboxOpen}
        onClose={() => setInboxOpen(false)}
        onRefresh={() => void fetchInbox(true, showAlert)}
        onSelectMessage={setActiveInboxIndex}
        subscriptions={subscriptions}
      />

      <HistoryModal
        histEnd={histEnd}
        histStart={histStart}
        historyDetailIndex={historyDetailIndex}
        historyItems={historyItems}
        historyLoading={historyLoading}
        historyOpen={historyOpen}
        onChangeEnd={setHistEnd}
        onChangeStart={setHistStart}
        onClose={() => setHistoryOpen(false)}
        onQuery={() => void fetchHistory(true, false, showAlert)}
        onSelectDetail={setHistoryDetailIndex}
      />

      <CustomModal
        actions={
          <MainModalActions
            modalKind={modalKind}
            purchaseDraft={purchaseDraft}
            transferSubmitting={transferSubmitting}
            onClose={closeCustomModal}
            onCheckout={() => showPurchaseModal(`购物车共 ${cart.length} 项商品`, cartTotal, 'cart')}
            onConfirmPurchase={() => {
              if (!purchaseDraft) return
              if (purchaseDraft.source === 'cart') void submitCheckout(showAlert)
              else void submitCmnPurchase(cmnData, selectedNumber, showAlert)
            }}
            onConfirmTransfer={() => void handleSubmitTransfer()}
          />
        }
        mode={modalMode}
        onClose={closeCustomModal}
        open={showModal}
        title={modalTitle}
      >
        {modalKind === 'alert' ? (alert.tone ? <StatusMessage message={alert.text} tone={alert.tone} /> : alert.text) : null}
        {modalKind === 'switch' ? <AccountSwitchModalContent availableAccounts={availableAccounts} currentSubId={currentSubId} onAddAccount={addAccount} onSwitchAccount={switchAccount} onSwitchSubscription={performSwitch} subscriptions={subscriptions} /> : null}
        {modalKind === 'cart' ? <CartModalContent cart={cart} onRemove={removeCartItem} onUpdateQuantity={updateCartItem} total={cartTotal} /> : null}
        {modalKind === 'purchase' && purchaseDraft ? <PurchaseModalContent balance={balance} draft={purchaseDraft} onChangeDraft={setPurchaseDraft} showNewLineOption={showFreePlans && purchaseDraft.source === 'cart'} /> : null}
        {modalKind === 'transfer' && transferDraft ? <TransferModalContent amount={transferAmount} draft={transferDraft} error={transferError} onChangeAmount={setTransferAmount} onChangeTarget={setTransferTarget} target={transferTarget} /> : null}
      </CustomModal>

      {cartQtyPresence.value !== null ? (
        <CartQuantityModal
          cart={cart}
          draft={cartQtyPresence.value}
          onCancel={() => setCartQtyDraft(null)}
          onConfirm={() => confirmAddToCart(showAlert)}
          onExitComplete={cartQtyPresence.completeExit}
          onUpdateDraft={setCartQtyDraft}
          phase={cartQtyPresence.phase}
        />
      ) : null}
    </>
  )
}

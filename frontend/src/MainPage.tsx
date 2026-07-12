import { useEffect, useMemo, useState } from 'react'
import { apiFetch, apiGet } from './api/client'
import { BUILD_VERSION } from './build'
import { AccountSwitchModalContent } from './components/AccountSwitchModalContent'
import { ActiveOffersSection } from './components/ActiveOffersSection'
import { CartFab } from './components/CartFab'
import { CartModalContent } from './components/CartModalContent'
import { CartQuantityModal } from './components/CartQuantityModal'
import { CmnSection } from './components/CmnSection'
import { CustomModal } from './components/CustomModal'
import { HistoryModal } from './components/HistoryModal'
import { InboxModal } from './components/InboxModal'
import { MainFooter } from './components/MainFooter'
import { MainHeader } from './components/MainHeader'
import { PlanList } from './components/PlanList'
import { PurchaseModalContent } from './components/PurchaseModalContent'
import { StatusMessage, type StatusTone } from './components/StatusMessage'
import { TransferModalContent } from './components/TransferModalContent'
import { useBodyScrollLock } from './hooks/useBodyScrollLock'
import { useCmn } from './hooks/useCmn'
import { useHistory } from './hooks/useHistory'
import { useInbox } from './hooks/useInbox'
import { isRootOpacityTransition, usePresenceValue } from './hooks/usePresenceValue'
import { usePurchaseCart } from './hooks/usePurchaseCart'
import { useServiceWorker } from './hooks/useServiceWorker'
import { useTransfer } from './hooks/useTransfer'
import type { AvailableAccount, Category, ModalMode, Plan, ProfileResponse, Subscription } from './types'
import { getAccountIdFromPathname, getApiUrl } from './utils/mainPage'

const SVG_SPRITE = `
<svg>
  <symbol id="icon-mail" viewBox="0 0 1024 1024"><path d="M128 224h768a64 64 0 0 1 64 64v448a64 64 0 0 1-64 64H128a64 64 0 0 1-64-64V288a64 64 0 0 1 64-64zm0 64v448h768V288L512 576 128 288zm384 226.24L834.24 224H189.76L512 514.24z" fill="currentColor"></path></symbol>
  <symbol id="icon-history" viewBox="0 0 1024 1024"><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="currentColor"/><path d="M686.7 638.6L544.1 535.5V288c0-4.4-3.6-8-8-8H488c-4.4 0-8 3.6-8 8v275.4c0 2.6 1.2 5 3.3 6.5l165.4 120.6c3.6 2.6 8.6 1.8 11.2-1.7l28.6-39c2.6-3.7 1.8-8.7-1.8-11.2z" fill="currentColor"/></symbol>
  <symbol id="icon-cart" viewBox="0 0 1024 1024"><path d="M922.9 277.3l-59.5 329.4c-4.4 24.2-25.5 41.8-50.1 41.8H311.2c-23.7 0-44.4-16.3-49.6-39.2L164.7 186H64c-17.7 0-32-14.3-32-32s14.3-32 32-32h120.4c24.6 0 46 17.6 50.3 41.9l12.4 69.4H900c21.6 0 37.1 20.8 30.2 41.3zM375.6 746c-31.1 0-56.4 25.3-56.4 56.4s25.3 56.4 56.4 56.4 56.4-25.3 56.4-56.4-25.3-56.4-56.4-56.4zm398.8 0c-31.1 0-56.4 25.3-56.4 56.4s25.3 56.4 56.4 56.4 56.4-25.3 56.4-56.4-25.3-56.4-56.4-56.4z" fill="currentColor"/></symbol>
</svg>`

type AlertState = { readonly text: string; readonly tone?: StatusTone }

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

  const [showModal, setShowModal] = useState(false)
  const [modalTitle, setModalTitle] = useState('标题')
  const [modalMode, setModalMode] = useState<ModalMode>('center')
  const [modalKind, setModalKind] = useState<'alert' | 'switch' | 'cart' | 'purchase' | 'transfer' | null>(null)
  const [alert, setAlert] = useState<AlertState>({ text: '' })

  const { openTransferModal, resetTransfer, setTransferAmount, setTransferTarget, submitTransfer, transferAmount, transferDraft, transferError, transferSubmitting, transferTarget } = useTransfer(accountId, currentSubId)

  const [refreshingUsage, setRefreshingUsage] = useState(false)

  const { checkCmnEligibility, cmnCanRefresh, cmnCooldown, cmnData, cmnError, cmnLoading, cmnNumbers, cmnNumbersLoading, cmnPattern, parsedCmnPattern, refreshCmnNumbers, selectedNumber, setCmnPattern, setSelectedNumber, submitChangeNumber } = useCmn(accountId, currentSubId)

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

  useEffect(() => {
    let cancelled = false
    const init = async (): Promise<void> => {
      try {
        const apiUrl = getApiUrl(`/api/profile?_t=${Date.now()}`, accountId)
        const response = await apiFetch(apiUrl, { headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' } })
        const contentType = response.headers.get('content-type')
        if (response.redirected || (contentType && !contentType.includes('application/json'))) {
          window.location.href = '/'
          return
        }
        if (!response.ok) throw new Error(`API Error: ${response.status}`)

        const data = (await response.json()) as ProfileResponse
        if (data.status !== 'success') {
          window.location.href = '/'
          return
        }
        if (cancelled) return

        const subs = data.data.subscriptions || []
        setSubscriptions(subs)
        setAvailableAccounts(data.data.available_accounts || [])
        const targetSub = (currentSubId ? subs.find((item) => item.subscriptionId === currentSubId) : null) || data.data.current || subs[0]
        if (targetSub?.subscriptionId) {
          setCurrentSubId(targetSub.subscriptionId)
        } else {
          setNoNumberMode(true)
        }
      } catch {
        // Login redirects are handled by the backend; keep the loader fallback silent here.
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void init()
    return () => {
      cancelled = true
    }
  }, [accountId, currentSubId])

  useEffect(() => {
    if (!currentSubId && !noNumberMode) return
    let cancelled = false

    const fetchBalance = async (): Promise<void> => {
      if (noNumberMode) { setBalance('0.0'); return }
      try {
        const url = getApiUrl(`/api/balance?subscriptionId=${currentSubId}&_t=${Date.now()}`, accountId)
        const data = await apiGet<{ status?: string; balance?: string | number }>(url)
        if (!cancelled) setBalance(data.status === 'success' ? String(data.balance ?? '0.0') : '0.0')
      } catch {
        if (!cancelled) setBalance('0.0')
      }
    }

    const fetchPlans = async (): Promise<void> => {
      setPlansLoading(true)
      try {
        const subParam = noNumberMode ? 'none' : currentSubId
        const url = getApiUrl(`/api/plans?subscriptionId=${subParam}`, accountId)
        const data = await apiGet<{ status?: string; plans?: Plan[] }>(url)
        if (!cancelled) setPlans(data.status === 'success' ? (data.plans || []).slice().sort((a, b) => a.price - b.price) : [])
      } catch {
        if (!cancelled) setPlans([])
      } finally {
        if (!cancelled) setPlansLoading(false)
      }
    }

    void fetchBalance()
    void fetchPlans()
    if (!noNumberMode) {
      void fetchInbox(false, showAlert)
      void fetchHistory(false, true, showAlert)
    }
    resetCart()
    resetHistory()
    if (category === 'CMN' && !noNumberMode) void checkCmnEligibility()

    return () => {
      cancelled = true
    }
    // fetchInbox/fetchHistory/checkCmnEligibility intentionally use current UI cache state;
    // including them would retrigger this initialization effect on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, category, currentSubId, noNumberMode])

  const showAlert = (text: string, title = '提示', tone?: StatusTone): void => {
    setModalKind('alert')
    setModalTitle(title)
    setModalMode('center')
    setAlert(tone ? { text, tone } : { text })
    setShowModal(true)
  }

  const closeCustomModal = (): void => {
    setShowModal(false)
    resetTransfer()
  }

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

  const openCartModal = (): void => {
    if (cart.length === 0) return
    setModalKind('cart')
    setModalTitle('购物车')
    setModalMode('center')
    setShowModal(true)
  }

  const showPurchaseModal = (title: string, price: number, source: 'cart' | 'cmn'): void => {
    openPurchaseModal(title, price, source, () => {
      setModalKind('purchase')
      setModalTitle('确认订单')
      setModalMode('center')
      setShowModal(true)
    })
  }

  const openSwitchModal = (): void => {
    setModalKind('switch')
    setModalTitle('账号管理')
    setModalMode('bottom-sheet')
    setShowModal(true)
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

  const renderModalActions = (): JSX.Element => {
    if (modalKind === 'alert') {
      return <button className="modal-btn confirm alert-ok" onClick={closeCustomModal}>关闭</button>
    }
    if (modalKind === 'switch') {
      return <></>
    }
    if (modalKind === 'cart') {
      return (
        <>
          <button className="modal-btn cancel" onClick={closeCustomModal}>取消</button>
          <button className="modal-btn confirm" onClick={() => showPurchaseModal(`购物车共 ${cart.length} 项商品`, cartTotal, 'cart')}>去结算</button>
        </>
      )
    }
    if (modalKind === 'purchase') {
      return (
        <>
          <button className="modal-btn cancel" onClick={closeCustomModal}>取消</button>
          <button
            className="modal-btn confirm"
            disabled={purchaseDraft?.submitting}
            onClick={() => {
              if (!purchaseDraft) return
              if (purchaseDraft.source === 'cart') void submitCheckout(showAlert)
              else void submitCmnPurchase(cmnData, selectedNumber, showAlert)
            }}
          >
            {purchaseDraft?.submitting ? '提交中…' : '确认'}
          </button>
        </>
      )
    }
    if (modalKind === 'transfer') {
      return (
        <>
          <button className="modal-btn cancel" onClick={closeCustomModal}>取消</button>
          <button className="modal-btn confirm" disabled={transferSubmitting} onClick={() => void handleSubmitTransfer()}>{transferSubmitting ? '处理中…' : '确认转移'}</button>
        </>
      )
    }
    return <></>
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

        <ActiveOffersSection currentSub={currentSub} onOpenTransfer={(event, draft) => openTransferModal(event, draft, () => { setModalKind('transfer'); setModalTitle('资源转移'); setModalMode('center'); setShowModal(true) })} onRefresh={() => void refreshProfileData()} onSelectOffer={setSelectedPlanId} refreshingUsage={refreshingUsage} selectedPlanId={selectedPlanId} visible={category === 'SUBSCRIBED'} />
        <CmnSection canRefresh={cmnCanRefresh} cooldown={cmnCooldown} data={cmnData} error={cmnError} loading={cmnLoading} numbers={cmnNumbers} numbersLoading={cmnNumbersLoading} onPatternChange={setCmnPattern} onRefresh={() => void refreshCmnNumbers(showAlert)} onSelectNumber={setSelectedNumber} onSubmit={() => submitChangeNumber(showAlert, showPurchaseModal)} parsedPattern={parsedCmnPattern} pattern={cmnPattern} selectedNumber={selectedNumber} visible={category === 'CMN'} />
        <MainFooter visible={category === 'ALL' || category === 'CMN'} />
      </div>

      <CartFab count={cartCount} onOpen={openCartModal} total={cartTotal} />

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

      <CustomModal actions={renderModalActions()} mode={modalMode} onClose={closeCustomModal} open={showModal} title={modalTitle}>
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

import { useEffect, useMemo, useState } from 'react'
import { apiFetch, apiGet } from './api/client'
import { BUILD_VERSION } from './build'
import { CartQuantityModal } from './components/CartQuantityModal'
import { HistoryModal } from './components/HistoryModal'
import { InboxModal } from './components/InboxModal'
import { MainHeader } from './components/MainHeader'
import { PlanList } from './components/PlanList'
import { useBodyScrollLock } from './hooks/useBodyScrollLock'
import { useCmn } from './hooks/useCmn'
import { useHistory } from './hooks/useHistory'
import { useInbox } from './hooks/useInbox'
import { usePurchaseCart } from './hooks/usePurchaseCart'
import { useServiceWorker } from './hooks/useServiceWorker'
import { useTransfer } from './hooks/useTransfer'
import type { AvailableAccount, Category, ModalMode, Plan, ProfileResponse, Subscription } from './types'
import { getAccountIdFromPathname, getApiUrl, normalizeUnit, stripHtml } from './utils/mainPage'

const SVG_SPRITE = `
<svg>
  <symbol id="icon-mail" viewBox="0 0 1024 1024"><path d="M128 224h768a64 64 0 0 1 64 64v448a64 64 0 0 1-64 64H128a64 64 0 0 1-64-64V288a64 64 0 0 1 64-64zm0 64v448h768V288L512 576 128 288zm384 226.24L834.24 224H189.76L512 514.24z" fill="currentColor"></path></symbol>
  <symbol id="icon-history" viewBox="0 0 1024 1024"><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="currentColor"/><path d="M686.7 638.6L544.1 535.5V288c0-4.4-3.6-8-8-8H488c-4.4 0-8 3.6-8 8v275.4c0 2.6 1.2 5 3.3 6.5l165.4 120.6c3.6 2.6 8.6 1.8 11.2-1.7l28.6-39c2.6-3.7 1.8-8.7-1.8-11.2z" fill="currentColor"/></symbol>
  <symbol id="icon-cart" viewBox="0 0 1024 1024"><path d="M922.9 277.3l-59.5 329.4c-4.4 24.2-25.5 41.8-50.1 41.8H311.2c-23.7 0-44.4-16.3-49.6-39.2L164.7 186H64c-17.7 0-32-14.3-32-32s14.3-32 32-32h120.4c24.6 0 46 17.6 50.3 41.9l12.4 69.4H900c21.6 0 37.1 20.8 30.2 41.3zM375.6 746c-31.1 0-56.4 25.3-56.4 56.4s25.3 56.4 56.4 56.4 56.4-25.3 56.4-56.4-25.3-56.4-56.4-56.4zm398.8 0c-31.1 0-56.4 25.3-56.4 56.4s25.3 56.4 56.4 56.4 56.4-25.3 56.4-56.4-25.3-56.4-56.4-56.4z" fill="currentColor"/></symbol>
</svg>`

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

  const { activeInboxIndex, fetchInbox, inboxLoading, inboxMessages, inboxOpen, openInbox, setActiveInboxIndex, setInboxOpen } = useInbox(accountId)

  const { fetchHistory, histEnd, histStart, historyDetailIndex, historyItems, historyLoading, historyOpen, openHistory, resetHistory, setHistEnd, setHistStart, setHistoryDetailIndex, setHistoryOpen } = useHistory(accountId, currentSubId)

  const [showModal, setShowModal] = useState(false)
  const [modalTitle, setModalTitle] = useState('标题')
  const [modalMode, setModalMode] = useState<ModalMode>('center')
  const [modalKind, setModalKind] = useState<'alert' | 'switch' | 'cart' | 'purchase' | 'transfer' | null>(null)
  const [alertText, setAlertText] = useState('')

  const { openTransferModal, resetTransfer, setTransferAmount, setTransferTarget, submitTransfer, transferAmount, transferDraft, transferError, transferSubmitting, transferTarget } = useTransfer(accountId, currentSubId)

  const [refreshingUsage, setRefreshingUsage] = useState(false)

  const { checkCmnEligibility, clearLongPress, cmnCanRefresh, cmnCooldown, cmnData, cmnError, cmnLoading, cmnNumbers, cmnNumbersLoading, refreshCmnNumbers, selectedNumber, setSelectedNumber, startLongPressEdit, submitChangeNumber } = useCmn(accountId, currentSubId)

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
  useBodyScrollLock(inboxOpen || historyOpen || showModal)

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

  const showAlert = (text: string, title = '提示'): void => {
    setModalKind('alert')
    setModalTitle(title)
    setModalMode('center')
    setAlertText(text)
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
    showAlert(`✅ 资源已成功转移给 ${target}`, '办理成功')
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

  const renderPurchase = purchaseDraft
    ? (() => {
        const currentBalance = Number.parseFloat(balance) || 0
        const maxAllowed = Math.min(currentBalance, purchaseDraft.price)
        const validTxn = Math.max(0, Math.min(purchaseDraft.txnAmount, maxAllowed))
        const payAmount = Math.max(0, purchaseDraft.price - validTxn)
        const isThree = showFreePlans && purchaseDraft.source === 'cart'
        return (
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: '14px', color: '#64748b' }}>商品信息</div>
            <div style={{ fontWeight: 700, fontSize: '16px', marginBottom: '15px', borderBottom: '1px solid #eee', paddingBottom: '10px' }}>{purchaseDraft.title}</div>
            {isThree && (
                <div
                  onClick={() => setPurchaseDraft((prev) => (prev ? { ...prev, newLine: !prev.newLine } : null))}
                  style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px', padding: '12px', borderRadius: '10px', border: `1.5px solid ${purchaseDraft.newLine ? '#774FDA' : '#e2e8f0'}`, background: purchaseDraft.newLine ? 'rgba(119,79,218,0.06)' : '#f8fafc', cursor: 'pointer', userSelect: 'none' }}
                >
                  <div style={{ width: '20px', height: '20px', borderRadius: '5px', border: `2px solid ${purchaseDraft.newLine ? '#774FDA' : '#cbd5e1'}`, background: purchaseDraft.newLine ? '#774FDA' : 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'all 0.2s' }}>
                    {purchaseDraft.newLine && <span style={{ color: 'white', fontSize: '13px', fontWeight: 700, lineHeight: 1 }}>✓</span>}
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '13px', color: purchaseDraft.newLine ? '#774FDA' : '#374151' }}>新开UFO</div>
                    <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>新开号码(GLOBAL_ESIM)</div>
                  </div>
                </div>
            )}
            <div style={{ marginBottom: '15px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}><span>余额抵扣</span><span style={{ color: '#64748b' }}>(可用: ${currentBalance})</span></div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontWeight: 'bold' }}>$</span>
                <input
                  type="number"
                  value={validTxn}
                  step="0.1"
                  max={maxAllowed}
                  min={0}
                  onChange={(event) => {
                    const next = Number.parseFloat(event.target.value)
                    setPurchaseDraft((prev) => (prev ? { ...prev, txnAmount: Number.isNaN(next) ? 0 : next } : null))
                  }}
                  style={{ width: '100%', padding: '10px', border: '1px solid #cbd5e1', borderRadius: '8px', fontWeight: 700 }}
                />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', fontWeight: 700 }}>
              <span>需支付</span><span style={{ fontSize: '18px', color: '#e53e3e' }}>${payAmount.toFixed(1)}</span>
            </div>
            <div id="modalPaySection" style={{ display: payAmount > 0.01 ? 'block' : 'none' }}>
              <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '8px' }}>补款方式</div>
              <div className="payment-grid">
                {(['ALCN', 'ALHK', 'WECHAT', 'MPGS'] as const).map((item) => (
                  <div key={item} className={`pay-opt ${purchaseDraft.paymentType === item ? 'selected' : ''}`} onClick={() => setPurchaseDraft((prev) => (prev ? { ...prev, paymentType: item } : null))}>
                    {item === 'ALCN' ? '支付宝' : item === 'ALHK' ? 'AlipayHK' : item === 'WECHAT' ? '微信' : '信用卡'}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )
      })()
    : null

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
            {purchaseDraft?.submitting ? '提交中...' : '确认'}
          </button>
        </>
      )
    }
    if (modalKind === 'transfer') {
      return (
        <>
          <button className="modal-btn cancel" onClick={closeCustomModal}>取消</button>
          <button className="modal-btn confirm" disabled={transferSubmitting} onClick={() => void handleSubmitTransfer()}>{transferSubmitting ? '处理中...' : '确认转移'}</button>
        </>
      )
    }
    return <></>
  }

  return (
    <>
      <div style={{ display: 'none' }} dangerouslySetInnerHTML={{ __html: SVG_SPRITE }} />
      <input type="hidden" id="current-account-id-ref" defaultValue={accountId} />
      <div id="global-loader" className={`global-loader ${loading ? '' : 'fade-out'}`} style={loading ? undefined : { display: 'none' }}>
        <div className="loader-content"><div className="spinner"></div><div className="loader-text">正在同步账户信息...</div></div>
      </div>

      <MainHeader availableAccounts={availableAccounts} balance={balance} category={category} currentSub={currentSub} noNumberMode={noNumberMode} onLogout={handleLogout} onOpenHistory={() => void openHistory(showAlert)} onOpenInbox={() => void openInbox(showAlert)} onOpenSwitch={openSwitchModal} onSearchChange={setSearch} onShowAlert={showAlert} onSwitchCategory={switchCategory} search={search} />

      <div className="content-wrapper">
        <PlanList filteredPlans={filteredPlans} noNumberMode={noNumberMode} onAddToCart={openAddToCart} onSelectPlan={setSelectedPlanId} plansLoading={plansLoading} selectedPlanId={selectedPlanId} showFreePlans={showFreePlans} visible={category !== 'SUBSCRIBED' && category !== 'CMN'} />

        <div id="activeOffersContainer" style={{ display: category === 'SUBSCRIBED' ? 'block' : 'none' }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '-10px', paddingBottom: '10px', paddingRight: '5px' }}>
            <button id="refreshUsageBtn" className="refresh-text-btn" disabled={refreshingUsage} onClick={() => void refreshProfileData()}>{refreshingUsage ? '同步中...' : '↻ 刷新用量'}</button>
          </div>
          <div id="activeOffersList" className="plan-list">
            {(currentSub?.activeOffers || []).map((offer) => {
              const isOpen = selectedPlanId === `sub-${offer.offerId}`
              let st = offer.planStatus || ''
              let sc = '#64748b'
              let sb = '#f1f5f9'
              if (st === 'ACTIVE') { st = '生效中'; sc = '#059669'; sb = '#d1fae5' }
              else if (st === 'PREACTIVE') { st = '待生效'; sc = '#d97706'; sb = '#fef3c7' }
              return (
                <div key={offer.offerId} className="plan-card" onClick={() => setSelectedPlanId(isOpen ? null : `sub-${offer.offerId}`)}>
                  {offer.isVoWifi ? <div className="tag-vowifi">VoWiFi</div> : null}
                  <div className="card-header"><div className="plan-name">{offer.name}</div><div className="plan-price">{offer.price ? `$${offer.price}` : ''}</div></div>
                  <div className="card-meta"><div style={{ display: 'flex', alignItems: 'center' }}><span style={{ background: sb, color: sc, padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 700, marginRight: '6px' }}>{st || '--'}</span><span className="validity-badge" style={{ background: '#e0f2fe', color: '#0369a1' }}>有效期至 {offer.endDate}</span></div><span className="arrow" style={{ transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span></div>
                  <div className={`card-details ${isOpen ? 'open' : ''}`}>
                    {offer.usage && offer.usage.length > 0 ? (
                      <div className="usage-section">
                        {offer.usage.map((u, index) => {
                          const unit = (u.unit || '').toLowerCase()
                          let totalLabel = `${Math.floor(u.total || 0)}${normalizeUnit(u.unit)}`
                          let remainLabel = `${Math.floor(u.remain || 0)}${normalizeUnit(u.unit)}`
                          if (unit === 'megabytes') {
                            const total = u.total || 0
                            const remain = u.remain || 0
                            totalLabel = total > 1024 ? `${(total / 1024).toFixed(1)}GB` : `${Math.floor(total)}MB`
                            remainLabel = remain > 1024 ? `${(remain / 1024).toFixed(1)}GB` : `${Math.floor(remain)}MB`
                          }
                          const percent = u.percent || 0
                          const barClass = `usage-bar ${percent < 20 ? 'critical' : percent < 50 ? 'low' : ''}`.trim()
                          return (
                            <div key={`${offer.offerId}-${index}`} className="usage-item">
                              <div className="usage-header">
                                <span>{u.name || '数据'}</span>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                                  <span>剩 {remainLabel} / 总 {totalLabel}</span>
                                  {u.canTransfer ? (
                                    <button
                                      className="trans-btn"
                                      onClick={(event) => openTransferModal(event, {
                                        userOfferId: offer.offerId,
                                        balanceResourceId: String(u.balanceResourceId || ''),
                                        unit: u.unit || '',
                                        minTransfer: u.minTransfer || 0,
                                        productFamily: u.productFamily || '',
                                        maxValue: u.remain || 0,
                                      }, () => {
                                        setModalKind('transfer')
                                        setModalTitle('资源转移')
                                        setModalMode('center')
                                        setShowModal(true)
                                      })}
                                    >转</button>
                                  ) : null}
                                </div>
                              </div>
                              <div className="usage-track"><div className={barClass} style={{ width: `${percent}%` }}></div></div>
                            </div>
                          )
                        })}
                      </div>
                    ) : null}
                    <div className="detail-desc">{offer.desc ? stripHtml(offer.desc) : ''}</div>
                  </div>
                </div>
              )
            })}
          </div>
          <div id="activeEmptyState" className="empty-state" style={{ display: (currentSub?.activeOffers || []).length === 0 ? 'block' : 'none' }}>当前没有已订购的生效套餐</div>
        </div>

        <div id="cmnContainer" style={{ display: category === 'CMN' ? 'block' : 'none' }}>
          <div className="cmn-view-card">
            <div className="cmn-header"><div className="cmn-title">更改电话号码服务</div><div className="cmn-desc">更换后原号码将立即失效</div></div>
            <div id="cmn-loading" className="loader" style={{ display: cmnLoading ? 'block' : 'none' }}>正在检查换号资格...</div>
            {cmnError ? <div style={{ color: 'var(--danger)', padding: '20px' }}>{cmnError}</div> : null}
            {cmnData && !cmnLoading ? (
              <div id="cmn-content" style={{ display: 'block' }}>
                <div className="cmn-body">
                  <div className="cmn-price-box"><div className="cmn-price-label">服务费用</div><div className="cmn-price-val">$<span id="cmn-price">{cmnData.price}</span></div><div className="cmn-price-tip">* ⚠️ 号码更换后，旧号码将立即失效且无法找回</div></div>
                  <div id="numbers-section">
                    <div id="initial-load-area" style={{ textAlign: 'center', padding: '10px 0 30px 0', display: (cmnNumbers.length > 0 || cmnNumbersLoading) ? 'none' : 'block' }}>
                      <button className="refresh-btn" id="initLoadBtn" onClick={() => void refreshCmnNumbers(showAlert)}><span>🔍</span> <span>获取一组新号码</span></button>
                    </div>
                    <div id="num-grid-wrapper" style={{ display: (cmnNumbers.length > 0 || cmnNumbersLoading) ? 'block' : 'none' }}>
                      <div style={{ fontSize: '12px', color: 'var(--text-sub)', marginBottom: '10px', display: 'flex', justifyContent: 'space-between' }}><span>选择心仪号码</span><span>长按可手填</span></div>
                      <div className="num-grid" id="numGrid">
                        {cmnNumbersLoading ? (
                          <div className="loader" style={{ gridColumn: 'span 3', padding: '20px' }}>正在获取号码库...</div>
                        ) : cmnNumbers.map((n) => (
                          <div
                            key={n}
                            className={`num-btn ${selectedNumber === n ? 'selected' : ''}`}
                            onClick={() => setSelectedNumber(n)}
                            onMouseDown={() => startLongPressEdit(n)}
                            onTouchStart={() => startLongPressEdit(n)}
                            onMouseUp={clearLongPress}
                            onMouseLeave={clearLongPress}
                            onTouchEnd={clearLongPress}
                            onTouchMove={clearLongPress}
                          >
                            {n}
                          </div>
                        ))}
                      </div>
                      <div className="cmn-actions">
                        <button className="refresh-btn" id="refreshNumBtn" disabled={!cmnCanRefresh} onClick={() => void refreshCmnNumbers(showAlert)}>{cmnCanRefresh ? '🔄 换一批' : `⏳ (`}<span id="refresh-timer">{cmnCanRefresh ? '' : `${cmnCooldown}s`}</span>{cmnCanRefresh ? '' : ')'}</button>
                        <button className="buy-btn" id="cmnBuyBtn" onClick={() => submitChangeNumber(showAlert, showPurchaseModal)}>确认支付并更换</button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div id="mainFooter" className="footer-note-main" style={{ display: category === 'ALL' || category === 'CMN' ? 'block' : 'none' }}>
          仅供个人学习使用，高净值账号请勿使用本网站。<br />
          <span>如使用密码登录请于24h内更改密码。<br />发生一切损失于本网站无关。</span>
          <br />
          <a href="https://example.invalid/support" target="_blank" rel="noopener noreferrer" className="support-link-main" aria-label="联系 external_delivery 客服"><svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 11.944 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" fill="currentColor" /></svg></a>
        </div>
      </div>

      <div id="cartFab" className="cart-fab" style={{ display: cartCount > 0 ? 'flex' : 'none' }} onClick={openCartModal}>
        <div className="cart-icon-wrapper"><svg className="icon"><use xlinkHref="#icon-cart"></use></svg><span id="cartCount" className="cart-badge">{cartCount}</span></div>
        <span className="cart-total-preview" id="cartTotalPreview">${cartTotal.toFixed(1)}</span>
      </div>

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

      <div id="customModal" className={`modal-overlay ${showModal ? 'show' : ''} ${modalMode === 'bottom-sheet' ? 'bottom-sheet-overlay' : ''}`} onClick={(event) => { if (event.target === event.currentTarget) closeCustomModal() }}>
        <div className="modal-box">
          <div className="modal-title" id="modalTitle">{modalTitle}</div>
          <div className="modal-text" id="modalText">
            {modalMode === 'bottom-sheet' ? <div className="modal-handle"></div> : null}
            {modalKind === 'alert' ? alertText : null}
            {modalKind === 'switch' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '10px' }}>
                {subscriptions.length > 0 ? (
                  <div>
                    <div style={{ fontSize: '13px', color: 'var(--text-sub)', marginBottom: '10px', fontWeight: 600 }}>当前账号号码</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {subscriptions.map((s) => {
                        const isCurr = s.subscriptionId === currentSubId
                        const statusIcon = s.status === 'ACTIVE' ? '🟢' : s.status === 'PREACTIVE' ? '🟠' : s.status === 'SUSPENDED' ? '🔴' : '⚪'
                        return (
                          <div key={s.subscriptionId} onClick={() => performSwitch(s)} style={{ padding: '14px', borderRadius: '16px', cursor: 'pointer', position: 'relative', transition: '0.2s', background: isCurr ? 'rgba(255, 123, 0, 0.05)' : 'var(--bg-card)', border: isCurr ? '1.5px solid var(--primary)' : '1px solid var(--border-color)' }}>
                            <div style={{ fontSize: '17px', fontWeight: 700, display: 'flex', justifyContent: 'space-between', color: isCurr ? 'var(--primary)' : 'var(--text-main)' }}><span>📱 {s.mobile}</span>{isCurr ? <span>✔</span> : null}</div>
                            <div style={{ fontSize: '12px', color: 'var(--text-sub)', marginTop: '6px', display: 'flex', justifyContent: 'space-between' }}><span>{statusIcon} {s.brand || '3HK'}</span><span style={{ fontFamily: 'monospace' }}>..{(s.iccid || '').slice(-4)}</span></div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ) : null}
                {availableAccounts.length > 0 ? (
                  <div>
                    <div style={{ fontSize: '13px', color: 'var(--text-sub)', marginBottom: '10px', fontWeight: 600 }}>切换其他账号</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {availableAccounts.map((acc) => (
                        <div key={acc.identifier} onClick={() => { if (!acc.active) switchAccount(acc.identifier) }} style={{ padding: '12px 14px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', border: '1px solid var(--border-color)', cursor: acc.active ? 'default' : 'pointer', background: acc.active ? 'var(--bg-secondary)' : 'var(--bg-card)', opacity: acc.active ? 0.6 : 1 }}>
                          <div style={{ display: 'flex', flexDirection: 'column' }}><div style={{ fontSize: '14px', fontWeight: 600 }}>👤 {acc.identifier}</div><div style={{ fontSize: '11px', color: 'var(--text-sub)' }}>{acc.subBrand}</div></div>
                          {acc.active ? <span style={{ fontSize: '10px', padding: '2px 8px', background: 'var(--border-color)', borderRadius: '6px' }}>当前</span> : <span style={{ color: 'var(--text-sub)', fontSize: '18px' }}>›</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                <button onClick={addAccount} style={{ width: '100%', padding: '14px', background: 'var(--bg-secondary)', border: '1px dashed var(--border-color)', color: 'var(--text-sub)', borderRadius: '14px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginTop: '8px' }}><span style={{ fontSize: '18px' }}>+</span> 添加账号</button>
              </div>
            ) : null}
            {modalKind === 'cart' ? (
              <div>
                <div className="cart-list">
                  {cart.map((item, index) => (
                    <div key={`${item.offerId}-${index}`} className="cart-item">
                      <div className="cart-item-info"><div className="cart-item-title">{item.name}</div><div className="cart-item-price">${item.price} x {item.quantity} = ${(item.price * item.quantity).toFixed(1)}</div></div>
                      <div className="cart-item-ctrl"><button className="cart-mini-btn" onClick={() => updateCartItem(index, -1)}>-</button><span style={{ fontWeight: 600, width: '20px', textAlign: 'center' }}>{item.quantity}</span><button className="cart-mini-btn" onClick={() => updateCartItem(index, 1)}>+</button><button className="cart-mini-btn cart-remove" onClick={() => removeCartItem(index)}>×</button></div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #eee', display: 'flex', justifyContent: 'space-between', fontWeight: 800, fontSize: '18px' }}><span>总计</span><span style={{ color: '#e53e3e' }}>${cartTotal.toFixed(1)}</span></div>
              </div>
            ) : null}
            {modalKind === 'purchase' ? renderPurchase : null}
            {modalKind === 'transfer' && transferDraft ? (
              <div style={{ textAlign: 'left' }}>
                <div style={{ fontSize: '14px', color: 'var(--text-sub)', marginBottom: '15px' }}>资源转移 ({normalizeUnit(transferDraft.unit)})</div>
                <div className="form-group" style={{ marginBottom: '15px' }}><label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>对方号码</label><input type="tel" value={transferTarget} onChange={(event) => setTransferTarget(event.target.value)} placeholder="输入 8 位手机号码" style={{ width: '100%', padding: '12px', border: '1px solid var(--border-color)', borderRadius: '12px', fontSize: '16px' }} /></div>
                <div className="form-group"><label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>转移数量 (可用: {Math.floor(transferDraft.maxValue)})</label><input type="number" value={transferAmount} onChange={(event) => setTransferAmount(event.target.value)} placeholder={`最少 ${transferDraft.minTransfer}`} style={{ width: '100%', padding: '12px', border: '1px solid var(--border-color)', borderRadius: '12px', fontSize: '16px' }} /></div>
                <div id="transErrorMsg" className="form-error-msg" style={{ display: transferError ? 'block' : 'none' }}>{transferError}</div>
              </div>
            ) : null}
          </div>
          <div className="modal-actions" id="modalActions">{renderModalActions()}</div>
        </div>
      </div>

      {cartQtyDraft ? (
        <CartQuantityModal
          cart={cart}
          draft={cartQtyDraft}
          onCancel={() => setCartQtyDraft(null)}
          onConfirm={() => confirmAddToCart(showAlert)}
          onUpdateDraft={setCartQtyDraft}
        />
      ) : null}
    </>
  )
}

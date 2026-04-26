import { useEffect, useMemo, useRef, useState } from 'react'
import DOMPurify from 'dompurify'

import { apiFetch, apiGet, apiPostJson } from './api/client'
import { BUILD_VERSION } from './build'
import { useBodyScrollLock } from './hooks/useBodyScrollLock'
import { useServiceWorker } from './hooks/useServiceWorker'
import type { AvailableAccount, CartItem, Category, CmnCheckResponse, HistoryItem, InboxMessage, ModalMode, Plan, ProfileResponse, Subscription, TransferDraft } from './types'
import { formatStatus, getAccountIdFromPathname, getApiUrl, getIsoTime, normalizeUnit, stripHtml } from './utils/mainPage'

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

  const [cart, setCart] = useState<CartItem[]>([])
  const [cartQtyDraft, setCartQtyDraft] = useState<{ offerId: string; name: string; price: number; quantity: number } | null>(null)

  const [inboxOpen, setInboxOpen] = useState(false)
  const [inboxLoading, setInboxLoading] = useState(false)
  const [inboxMessages, setInboxMessages] = useState<InboxMessage[]>([])
  const [activeInboxIndex, setActiveInboxIndex] = useState<number | null>(null)

  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([])
  const [historyDetailIndex, setHistoryDetailIndex] = useState<number | null>(null)
  const [histStart, setHistStart] = useState('')
  const [histEnd, setHistEnd] = useState('')
  const [historyCache, setHistoryCache] = useState<Record<string, HistoryItem[]>>({})

  const [showModal, setShowModal] = useState(false)
  const [modalTitle, setModalTitle] = useState('标题')
  const [modalMode, setModalMode] = useState<ModalMode>('center')
  const [modalKind, setModalKind] = useState<'alert' | 'switch' | 'cart' | 'purchase' | 'transfer' | null>(null)
  const [alertText, setAlertText] = useState('')

  const [purchaseDraft, setPurchaseDraft] = useState<{ title: string; price: number; txnAmount: number; paymentType: 'ALCN' | 'ALHK' | 'WECHAT' | 'MPGS'; submitting: boolean; source: 'cart' | 'cmn'; newLine: boolean } | null>(null)

  const [transferDraft, setTransferDraft] = useState<TransferDraft | null>(null)
  const [transferTarget, setTransferTarget] = useState('')
  const [transferAmount, setTransferAmount] = useState('')
  const [transferError, setTransferError] = useState('')
  const [transferSubmitting, setTransferSubmitting] = useState(false)

  const [refreshingUsage, setRefreshingUsage] = useState(false)

  const [cmnLoading, setCmnLoading] = useState(false)
  const [cmnError, setCmnError] = useState('')
  const [cmnData, setCmnData] = useState<CmnCheckResponse['data'] | null>(null)
  const [cmnNumbers, setCmnNumbers] = useState<string[]>([])
  const [cmnNumbersLoading, setCmnNumbersLoading] = useState(false)
  const [selectedNumber, setSelectedNumber] = useState<string | null>(null)
  const [cmnCanRefresh, setCmnCanRefresh] = useState(true)
  const [cmnCooldown, setCmnCooldown] = useState(0)

  const longPressRef = useRef<number | null>(null)

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

  const cartCount = useMemo(() => cart.reduce((acc, item) => acc + item.quantity, 0), [cart])
  const cartTotal = useMemo(() => cart.reduce((acc, item) => acc + item.price * item.quantity, 0), [cart])

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
      void fetchInbox(false)
      void fetchHistory(false, true)
    }
    setCart([])
    setHistoryItems([])
    setHistoryDetailIndex(null)
    if (category === 'CMN' && !noNumberMode) void checkCmnEligibility()

    return () => {
      cancelled = true
    }
    // fetchInbox/fetchHistory/checkCmnEligibility intentionally use current UI cache state;
    // including them would retrigger this initialization effect on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, category, currentSubId, noNumberMode])

  useEffect(() => {
    if (cmnCooldown <= 0) return
    const timer = window.setInterval(() => {
      setCmnCooldown((prev) => {
        const next = prev - 1
        if (next <= 0) {
          setCmnCanRefresh(true)
          window.clearInterval(timer)
          return 0
        }
        return next
      })
    }, 1000)
    return () => window.clearInterval(timer)
  }, [cmnCooldown])

  const showAlert = (text: string, title = '提示'): void => {
    setModalKind('alert')
    setModalTitle(title)
    setModalMode('center')
    setAlertText(text)
    setShowModal(true)
  }

  const closeCustomModal = (): void => {
    setShowModal(false)
    setTransferError('')
    setTransferSubmitting(false)
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

  const openInbox = async (): Promise<void> => {
    setInboxOpen(true)
    if (inboxMessages.length === 0) await fetchInbox(true)
  }

  const fetchInbox = async (force: boolean): Promise<void> => {
    if (!force && inboxMessages.length > 0) return
    setInboxLoading(true)
    try {
      const url = getApiUrl('/api/inbox', accountId)
      const d = await apiGet<{ status?: string; messages?: InboxMessage[] }>(url)
      if (d.status === 'success') setInboxMessages(d.messages || [])
      else if (inboxOpen) showAlert('加载失败')
    } catch {
      if (inboxOpen) showAlert('加载失败')
    } finally {
      setInboxLoading(false)
    }
  }

  const openHistory = async (): Promise<void> => {
    const now = new Date()
    if (!histStart || !histEnd) {
      setHistStart(new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0])
      setHistEnd(new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0])
    }
    setHistoryOpen(true)
    if (historyItems.length === 0) await fetchHistory(true)
  }

  const fetchHistory = async (manual = false, silent = false): Promise<void> => {
    if (!currentSubId) return
    const now = new Date()
    const start = histStart || new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0]
    const end = histEnd || new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0]
    const startStr = getIsoTime(new Date(start))
    const endStr = getIsoTime(new Date(end), true)
    const cacheKey = `${currentSubId}_${startStr}_${endStr}`
    if (!manual && historyCache[cacheKey]) {
      setHistoryItems(historyCache[cacheKey])
      return
    }
    if (!silent) setHistoryLoading(true)
    try {
      const url = getApiUrl(`/api/history?subscriptionId=${currentSubId}&startDate=${startStr}&endDate=${endStr}&_t=${Date.now()}`, accountId)
      const d = await apiGet<{ status?: string; data?: HistoryItem[]; message?: string }>(url)
      if (d.status === 'success') {
        const next = d.data || []
        setHistoryItems(next)
        setHistoryCache((prev) => ({ ...prev, [cacheKey]: next }))
      } else if (!silent) {
        showAlert(d.message || '查询失败')
      }
    } catch {
      if (!silent) showAlert('网络错误')
    } finally {
      if (!silent) setHistoryLoading(false)
    }
  }

  const openAddToCart = (event: React.MouseEvent, plan: Plan): void => {
    event.stopPropagation()
    const existing = cart.find((x) => x.offerId === plan.offerId)
    setCartQtyDraft({ offerId: plan.offerId, name: plan.name, price: plan.price, quantity: existing?.quantity || 1 })
  }

  const confirmAddToCart = (): void => {
    if (!cartQtyDraft) return
    const quantity = Math.max(1, Math.min(99, cartQtyDraft.quantity))
    setCart((prev) => {
      const idx = prev.findIndex((x) => x.offerId === cartQtyDraft.offerId)
      if (idx >= 0) {
        const next = prev.slice()
        next[idx] = { ...next[idx], quantity }
        return next
      }
      return [...prev, { offerId: cartQtyDraft.offerId, name: cartQtyDraft.name, price: cartQtyDraft.price, quantity }]
    })
    setCartQtyDraft(null)
    showAlert(`已加入: ${cartQtyDraft.name} x ${quantity}`, '成功')
  }

  const openCartModal = (): void => {
    if (cart.length === 0) return
    setModalKind('cart')
    setModalTitle('购物车')
    setModalMode('center')
    setShowModal(true)
  }

  const openSwitchModal = (): void => {
    setModalKind('switch')
    setModalTitle('账号管理')
    setModalMode('bottom-sheet')
    setShowModal(true)
  }

  const updateCartItem = (index: number, delta: number): void => {
    setCart((prev) => {
      const next = prev.slice()
      next[index] = { ...next[index], quantity: next[index].quantity + delta }
      if (next[index].quantity <= 0) next.splice(index, 1)
      return next
    })
  }

  const removeCartItem = (index: number): void => {
    setCart((prev) => prev.filter((_, i) => i !== index))
  }

  const openPurchaseModal = (title: string, price: number, source: 'cart' | 'cmn'): void => {
    const currentBalance = Number.parseFloat(balance) || 0
    const txn = currentBalance >= price ? price : Math.max(currentBalance, 0)
    setPurchaseDraft({ title, price, txnAmount: txn, paymentType: 'ALCN', submitting: false, source, newLine: false })
    setModalKind('purchase')
    setModalTitle('确认订单')
    setModalMode('center')
    setShowModal(true)
  }

  const submitCheckout = async (): Promise<void> => {
    if (!purchaseDraft || purchaseDraft.source !== 'cart') return
    setPurchaseDraft((prev) => (prev ? { ...prev, submitting: true } : null))
    try {
      const url = getApiUrl('/api/purchase', accountId)
      const d = await apiPostJson<{ status?: string; message?: string; paymentUrl?: string }>(url, {
          items: cart,
          subscriptionId: currentSubId,
          price: purchaseDraft.price,
          paymentType: purchaseDraft.paymentType,
          txnAmount: purchaseDraft.txnAmount,
          new_line: purchaseDraft.newLine,
          account_id: accountId,
        })
      if (d.status === 'success' && d.paymentUrl) {
        setCart([])
        window.location.href = d.paymentUrl
      } else {
        showAlert(d.message || '提交失败', '错误')
        setPurchaseDraft((prev) => (prev ? { ...prev, submitting: false } : null))
      }
    } catch {
      showAlert('网络错误', '错误')
      setPurchaseDraft((prev) => (prev ? { ...prev, submitting: false } : null))
    }
  }

  const submitChangeNumber = async (): Promise<void> => {
    if (!selectedNumber) {
      showAlert('请先选择号码', '提示')
      return
    }
    if (!cmnData) return
    openPurchaseModal(`更换号码: ${selectedNumber}`, cmnData.price, 'cmn')
  }

  const submitCmnPurchase = async (): Promise<void> => {
    if (!purchaseDraft || purchaseDraft.source !== 'cmn' || !cmnData || !selectedNumber) return
    setPurchaseDraft((prev) => (prev ? { ...prev, submitting: true } : null))
    try {
      const url = getApiUrl('/api/cmn/purchase', accountId)
      const d = await apiPostJson<{ status?: string; paymentUrl?: string; message?: string }>(url, {
          offerId: cmnData.offerId,
          offerSubType: cmnData.offerSubType,
          price: cmnData.price,
          subscriptionId: currentSubId,
          selectedNumber,
          paymentType: purchaseDraft.paymentType,
          txnAmount: purchaseDraft.txnAmount,
          account_id: accountId,
        })
      if (d.status === 'success' && d.paymentUrl) {
        window.location.href = d.paymentUrl
      } else {
        showAlert(d.message || '提交失败', '失败')
        setPurchaseDraft((prev) => (prev ? { ...prev, submitting: false } : null))
      }
    } catch {
      showAlert('网络错误', '错误')
      setPurchaseDraft((prev) => (prev ? { ...prev, submitting: false } : null))
    }
  }

  const checkCmnEligibility = async (): Promise<void> => {
    if (!currentSubId) return
    setCmnLoading(true)
    setCmnError('')
    try {
      const url = getApiUrl(`/api/cmn/check?subscriptionId=${currentSubId}`, accountId)
      const d = await apiGet<CmnCheckResponse>(url)
      if (d.status === 'success' && d.data) {
        setCmnData(d.data)
      } else {
        setCmnData(null)
        setCmnError(d.message || '无法使用换号服务')
      }
    } catch {
      setCmnData(null)
      setCmnError('网络错误')
    } finally {
      setCmnLoading(false)
    }
  }

  const refreshCmnNumbers = async (): Promise<void> => {
    if (!cmnCanRefresh || !currentSubId) return
    setCmnCanRefresh(false)
    setCmnNumbersLoading(true)
    setCmnNumbers([])
    try {
      const url = getApiUrl(`/api/cmn/numbers?subscriptionId=${currentSubId}`, accountId)
      const d = await apiGet<{ status?: string; numbers?: string[]; message?: string }>(url)
      if (d.status === 'success') {
        setSelectedNumber(null)
        setCmnNumbers(d.numbers || [])
        setCmnCooldown(60)
      } else {
        setCmnCanRefresh(true)
        showAlert(d.message || '获取号码失败')
      }
    } catch {
      setCmnCanRefresh(true)
      showAlert('请求失败')
    } finally {
      setCmnNumbersLoading(false)
    }
  }

  const startLongPressEdit = (n: string): void => {
    longPressRef.current = window.setTimeout(() => {
      const edited = window.prompt('手动编辑:', n)
      if (!edited || !edited.trim()) return
      const value = edited.trim()
      setCmnNumbers((prev) => prev.map((item) => (item === n ? value : item)))
      setSelectedNumber(value)
    }, 800)
  }

  const clearLongPress = (): void => {
    if (longPressRef.current) {
      window.clearTimeout(longPressRef.current)
      longPressRef.current = null
    }
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

  const openTransferModal = (event: React.MouseEvent, draft: TransferDraft): void => {
    event.stopPropagation()
    setTransferDraft(draft)
    setTransferTarget('')
    setTransferAmount('')
    setTransferError('')
    setModalKind('transfer')
    setModalTitle('资源转移')
    setModalMode('center')
    setShowModal(true)
  }

  const submitTransfer = async (): Promise<void> => {
    if (!transferDraft || !currentSub) return
    const target = transferTarget.trim()
    const amount = Number.parseFloat(transferAmount)
    if (!target || target.length < 8) {
      setTransferError('❌ 请输入有效的手机号码')
      return
    }
    if (!amount || Number.isNaN(amount)) {
      setTransferError('❌ 请输入转移数量')
      return
    }
    if (amount < transferDraft.minTransfer) {
      setTransferError(`❌ 转移数量不能少于 ${transferDraft.minTransfer}`)
      return
    }
    if (amount > transferDraft.maxValue) {
      setTransferError('❌ 余额不足')
      return
    }

    setTransferSubmitting(true)
    setTransferError('')
    try {
      const url = getApiUrl('/api/sim/transfer', accountId)
      const d = await apiPostJson<{ status?: string; message?: string }>(url, {
          subscriptionId: currentSubId,
          sourceMsisdn: currentSub.mobile,
          targetMsisdn: target,
          amount,
          userOfferId: transferDraft.userOfferId,
          balanceResourceId: transferDraft.balanceResourceId,
          unit: transferDraft.unit,
          productFamily: transferDraft.productFamily,
          account_id: accountId,
        })
      if (d.status === 'success') {
        closeCustomModal()
        showAlert(`✅ 资源已成功转移给 ${target}`, '办理成功')
        void refreshProfileData()
      } else {
        setTransferSubmitting(false)
        setTransferError(`❌ ${d.message || '转移失败'}`)
      }
    } catch {
      setTransferSubmitting(false)
      setTransferError('❌ 网络请求失败')
    }
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
          <button className="modal-btn confirm" onClick={() => openPurchaseModal(`购物车共 ${cart.length} 项商品`, cartTotal, 'cart')}>去结算</button>
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
              if (purchaseDraft.source === 'cart') void submitCheckout()
              else void submitCmnPurchase()
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
          <button className="modal-btn confirm" disabled={transferSubmitting} onClick={() => void submitTransfer()}>{transferSubmitting ? '处理中...' : '确认转移'}</button>
        </>
      )
    }
    return <></>
  }

  const historyDetail = historyDetailIndex !== null ? historyItems[historyDetailIndex] : null
  const activeInboxContent = activeInboxIndex !== null ? inboxMessages[activeInboxIndex]?.content || '' : ''
  const safeActiveInboxContent = useMemo(() => DOMPurify.sanitize(activeInboxContent), [activeInboxContent])

  return (
    <>
      <div style={{ display: 'none' }} dangerouslySetInnerHTML={{ __html: SVG_SPRITE }} />
      <input type="hidden" id="current-account-id-ref" defaultValue={accountId} />
      <div id="global-loader" className={`global-loader ${loading ? '' : 'fade-out'}`} style={loading ? undefined : { display: 'none' }}>
        <div className="loader-content"><div className="spinner"></div><div className="loader-text">正在同步账户信息...</div></div>
      </div>

      <div className="fixed-header-wrapper">
        <div className="container" style={{ paddingBottom: 0 }}>
          <div className="mini-user-card">
            <div className="user-main">
              <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span id="u_mobile">{noNumberMode ? '无号码账号' : (currentSub?.mobile || '加载中...')}</span>
                <span id="u_switch_hint" style={{ display: availableAccounts.length > 0 ? 'inline-block' : 'none', cursor: 'pointer' }} onClick={openSwitchModal}>▼ 切换</span>
              </h2>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#2d3748', margin: '5px 0 2px 0', display: noNumberMode ? 'none' : 'flex', alignItems: 'center' }}>
                <span style={{ fontSize: '14px', color: '#64748b', fontWeight: 600, marginRight: '2px' }}>$</span>
                <span id="u_balance">{balance}</span>
                <button className="topup-mini-btn" onClick={() => currentSub?.mobile ? window.open(`https://www.three.com.hk/prepaid/account/tc/topup/${currentSub.mobile}`, '_blank') : showAlert('无法获取当前手机号')}>充值</button>
              </div>
              <div className="user-sub" id="u_dates_container" style={{ display: noNumberMode ? 'none' : undefined }}>
                {currentSub?.activationDate ? <span>{currentSub.activationDate} 激活</span> : null}
                {currentSub?.activationDate && currentSub?.subsEndDate ? ' · ' : null}
                {currentSub?.subsEndDate ? <span>{currentSub.subsEndDate} 到期</span> : null}
              </div>
              <div className="user-sub" style={{ marginTop: '4px', fontSize: '11px', opacity: 0.85, display: noNumberMode ? 'none' : undefined }}>
                <span id="u_status_badge" style={{ fontWeight: 700, color: formatStatus(currentSub?.status).color }}>{formatStatus(currentSub?.status).text}</span> · ICCID: <span id="u_iccid">{currentSub?.iccid || '--'}</span>
              </div>
            </div>
            <div className="user-actions" style={{ display: noNumberMode ? 'none' : undefined }}>
              <button className="icon-btn" aria-label="交易记录" onClick={() => void openHistory()}><svg className="icon"><use xlinkHref="#icon-history"></use></svg></button>
              <button className="icon-btn" aria-label="收件箱" onClick={() => void openInbox()}><svg className="icon"><use xlinkHref="#icon-mail"></use></svg></button>
              <a href="javascript:void(0)" onClick={handleLogout} className="logout-btn-icon" aria-label="退出登录">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M16 13v-2H7V8l-5 4 5 4v-3z"></path><path d="M20 3h-9c-1.103 0-2 .897-2 2v4h2V5h9v14h-9v-4H9v4c0 1.103.897 2 2 2h9c1.103 0 2-.897 2-2V5c0-1.103-.897-2-2-2z"></path></svg>
              </a>
            </div>
          </div>

          <div className="toolbar">
            <div className="search-box" id="searchBoxContainer" style={{ display: category === 'CMN' || category === 'SUBSCRIBED' ? 'none' : undefined }}>
              <input type="text" id="searchInput" placeholder="搜索套餐..." value={search} onChange={(event) => setSearch(event.target.value)} />
            </div>
            <div className="category-tabs">
              {(noNumberMode ? ['ALL', 'LOCAL', 'TRAVEL', 'OTHER'] as Category[] : ['ALL', 'LOCAL', 'TRAVEL', 'SUBSCRIBED', 'OTHER', 'CMN'] as Category[]).map((item) => (
                <div key={item} className={`cat-tab ${category === item ? 'active' : ''}`} style={item === 'CMN' ? { color: '#e53e3e' } : undefined} onClick={() => switchCategory(item)}>
                  {item === 'ALL' ? '全部' : item === 'LOCAL' ? '本地' : item === 'TRAVEL' ? '外遊' : item === 'SUBSCRIBED' ? '已订购' : item === 'OTHER' ? '其他' : '更换号码'}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="content-wrapper">
        <div id="planListContainer" style={{ display: category === 'SUBSCRIBED' || category === 'CMN' ? 'none' : undefined }}>
          <div id="planList" className="plan-list">
            {plansLoading ? <div className="loader">正在加载套餐...</div> : filteredPlans.map((plan) => {
              const isOpen = selectedPlanId === plan.offerId
              return (
                <div key={plan.offerId} className="plan-card" onClick={() => setSelectedPlanId(isOpen ? null : plan.offerId)}>
                  {plan.isVoWifi ? <div className="tag-vowifi">VoWiFi</div> : null}
                  <div className="card-header"><div className="plan-name">{plan.name}</div><div className="plan-price">${plan.price}</div></div>
                  <div className="card-meta"><span className="validity-badge">📅 {plan.validity}</span><span className="arrow" style={{ transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span></div>
                  <div className={`card-details ${isOpen ? 'open' : ''}`}>
                    <div className="detail-desc">{stripHtml(plan.desc)}</div>
                    <button className="buy-btn" type="button" style={{ display: (noNumberMode && !showFreePlans) ? 'none' : undefined }} onClick={(event) => openAddToCart(event, plan)}>加入购物车</button>
                  </div>
                </div>
              )
            })}
          </div>
          <div id="emptyState" className="empty-state" style={{ display: !plansLoading && filteredPlans.length === 0 ? 'block' : 'none' }}>无匹配结果</div>
        </div>

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
                      <button className="refresh-btn" id="initLoadBtn" onClick={() => void refreshCmnNumbers()}><span>🔍</span> <span>获取一组新号码</span></button>
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
                        <button className="refresh-btn" id="refreshNumBtn" disabled={!cmnCanRefresh} onClick={() => void refreshCmnNumbers()}>{cmnCanRefresh ? '🔄 换一批' : `⏳ (`}<span id="refresh-timer">{cmnCanRefresh ? '' : `${cmnCooldown}s`}</span>{cmnCanRefresh ? '' : ')'}</button>
                        <button className="buy-btn" id="cmnBuyBtn" onClick={() => void submitChangeNumber()}>确认支付并更换</button>
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

      <div id="inboxModal" className={`modal-overlay ${inboxOpen ? 'show' : ''}`} onClick={(event) => { if (event.target === event.currentTarget) setInboxOpen(false) }}>
        <div className="modal-box" style={{ maxWidth: '400px', padding: '20px 0', height: '80vh', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '0 20px 15px 20px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <div className="modal-title" style={{ margin: 0 }}>收件箱</div>
            <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
              <div id="inboxRefresh" style={{ color: '#64748b', fontSize: '18px', cursor: 'pointer' }} onClick={() => void fetchInbox(true)}>↻</div>
              <div style={{ color: '#94a3b8', fontSize: '24px', cursor: 'pointer', lineHeight: 1 }} onClick={() => setInboxOpen(false)}>&times;</div>
            </div>
          </div>
          <div id="inboxContent" style={{ padding: 0, flex: 1, overflowY: 'auto' }}>
            {inboxLoading ? <div className="loader" style={{ padding: '20px' }}>加载中...</div> : activeInboxIndex === null ? (
              inboxMessages.length === 0 ? <div className="empty-state">暂无消息</div> : <div className="inbox-list-container">{inboxMessages.map((msg, index) => {
                const dateStr = (msg.post_dt || '').replace('T', ' ').split('+')[0].slice(0, 16)
                const mobile = subscriptions.find((item) => item.subscriptionId === msg.intended_subscription_id)?.mobile || msg.intended_subscription_id
                return <div key={`${msg.subject}-${index}`} className="inbox-item" onClick={() => setActiveInboxIndex(index)}><div className="inbox-subject">{msg.subject}</div><div className="inbox-meta"><span>📱 {mobile}</span><span>{dateStr}</span></div></div>
              })}</div>
            ) : (
              <div style={{ padding: 0 }}>
                <div className="inbox-back-header" onClick={() => setActiveInboxIndex(null)}><span>← 返回</span></div>
                <div style={{ padding: '0 20px' }}>
                  <div style={{ marginBottom: '15px' }}><div style={{ fontSize: '16px', fontWeight: 700, marginBottom: '5px' }}>{inboxMessages[activeInboxIndex]?.subject}</div><div style={{ fontSize: '12px', color: '#94a3b8' }}>{(inboxMessages[activeInboxIndex]?.post_dt || '').replace('T', ' ').split('+')[0]}</div></div>
                  <div className="inbox-detail" dangerouslySetInnerHTML={{ __html: safeActiveInboxContent }}></div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div id="historyModal" className={`modal-overlay ${historyOpen ? 'show' : ''}`} onClick={(event) => { if (event.target === event.currentTarget) setHistoryOpen(false) }}>
        <div className="modal-box" style={{ maxWidth: '400px', padding: '20px 0', height: '80vh', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '0 20px 15px 20px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <div className="modal-title" style={{ margin: 0 }}>交易记录</div>
            <div style={{ color: '#94a3b8', fontSize: '24px', cursor: 'pointer', lineHeight: 1 }} onClick={() => setHistoryOpen(false)}>&times;</div>
          </div>
          <div className="history-filter-bar">
            <input type="date" id="histStart" className="date-input" value={histStart} onChange={(event) => setHistStart(event.target.value)} />
            <span style={{ color: '#94a3b8' }}>至</span>
            <input type="date" id="histEnd" className="date-input" value={histEnd} onChange={(event) => setHistEnd(event.target.value)} />
            <button className="filter-btn" disabled={historyLoading} onClick={() => void fetchHistory(true)}>{historyLoading ? '查询中...' : '查询'}</button>
          </div>
          <div id="historyContent" style={{ padding: 0, flex: 1, overflowY: 'auto' }}>
            {historyLoading ? <div className="loader" style={{ padding: '20px' }}>加载中...</div> : historyDetail ? (
              <div style={{ padding: 0 }}>
                <div className="inbox-back-header" onClick={() => setHistoryDetailIndex(null)}><span>← 返回</span></div>
                <div style={{ padding: '0 20px' }}>
                  <div style={{ fontSize: '24px', fontWeight: 800, textAlign: 'center' }}>${Number(historyDetail.purchase?.paymentDetail?.amnt || 0).toFixed(1)}</div>
                  <div style={{ textAlign: 'center', fontSize: '13px', color: 'var(--text-sub)', marginBottom: '20px' }}>交易金额</div>
                  <div className="cart-list" style={{ padding: 0 }}>
                    <div className="cart-item"><span>状态</span><span>{historyDetail.purchase?.purchaseStatus || '--'}</span></div>
                    <div className="cart-item"><span>时间</span><span>{(historyDetail.transactionDate || '').replace('T', ' ')}</span></div>
                    <div className="cart-item"><span>单号</span><span>{historyDetail.purchase?.purchaseId || '--'}</span></div>
                  </div>
                </div>
              </div>
            ) : historyItems.length === 0 ? <div className="empty-state">该时段无交易记录</div> : (
              <div className="inbox-list-container">
                {historyItems.map((item, index) => {
                  const p = item.purchase || {}
                  const dateStr = (item.transactionDate || '').replace('T', ' ').split('.')[0]
                  const status = p.purchaseStatus || 'UNKNOWN'
                  const statusColor = status === 'SUCCESS' ? '#10b981' : (status === 'CANCEL' || status === 'FAILED' ? '#e53e3e' : '#f59e0b')
                  const amount = p.paymentDetail ? (p.paymentDetail.amnt || p.paymentDetail.walletAmt || 0) : 0
                  const title = p.purchaseType === 'PREPAID_RECHARGE' ? '充值' : (p.purchaseType === 'SOSIM_VAS' ? '购买套餐' : item.type || '未知')
                  return (
                    <div key={`${title}-${index}`} className="inbox-item" onClick={() => setHistoryDetailIndex(index)}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}><div style={{ fontWeight: 600 }}>{title}</div><div style={{ fontWeight: 700, color: statusColor }}>${Number(amount).toFixed(1)}</div></div>
                      <div className="inbox-meta"><span>{dateStr}</span><span>{status}</span></div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>

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
        <div id="customModal" className="modal-overlay show" onClick={(event) => { if (event.target === event.currentTarget) setCartQtyDraft(null) }}>
          <div className="modal-box">
            <div className="modal-title">{cart.some((x) => x.offerId === cartQtyDraft.offerId) ? '调整数量' : '加入购物车'}</div>
            <div className="modal-text" style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '14px', color: '#64748b' }}>{cartQtyDraft.name}</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: '#FF7B00', margin: '10px 0' }}>${cartQtyDraft.price} / 件</div>
              <div className="qty-selector"><button className="qty-btn" onClick={() => setCartQtyDraft((prev) => (prev ? { ...prev, quantity: Math.max(1, prev.quantity - 1) } : null))}>-</button><input type="number" className="qty-input" value={cartQtyDraft.quantity} min={1} max={99} onChange={(event) => setCartQtyDraft((prev) => (prev ? { ...prev, quantity: Math.max(1, Math.min(99, Number.parseInt(event.target.value || '1', 10) || 1)) } : null))} /><button className="qty-btn" onClick={() => setCartQtyDraft((prev) => (prev ? { ...prev, quantity: Math.min(99, prev.quantity + 1) } : null))}>+</button></div>
            </div>
            <div className="modal-actions"><button className="modal-btn cancel" onClick={() => setCartQtyDraft(null)}>取消</button><button className="modal-btn confirm" onClick={confirmAddToCart}>确定</button></div>
          </div>
        </div>
      ) : null}
    </>
  )
}

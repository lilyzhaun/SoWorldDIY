import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'

import { useCmn } from '@/hooks/useCmn'

const wait = (milliseconds: number): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, milliseconds))
const realDateNow = Date.now.bind(Date)
let clockOffset = 0
let eligibilityRequestCount = 0
let numbersRequestCount = 0
let oldEligibilityAborted = false
let oldNumbersAborted = false
let autoRequestAborted = false
let resolveOldEligibility: (() => void) | null = null
let resolveOldNumbers: (() => void) | null = null
const requestUrls: string[] = []

Date.now = (): number => realDateNow() + clockOffset

window.fetch = async (input, init): Promise<Response> => {
  const url = String(input)
  const method = (init?.method || 'GET').toUpperCase()
  requestUrls.push(`${method} ${url}`)

  if (url.includes('/api/cmn/check')) {
    eligibilityRequestCount += 1
    if (eligibilityRequestCount === 1) {
      return new Promise((resolve, reject) => {
        resolveOldEligibility = () =>
          resolve(Response.json({ status: 'success', data: { offerId: 'old-offer', price: 1 } }))
        init?.signal?.addEventListener(
          'abort',
          () => {
            oldEligibilityAborted = true
            reject(new DOMException('Aborted', 'AbortError'))
          },
          { once: true },
        )
      })
    }
    return Response.json({ status: 'success', data: { offerId: 'new-offer', price: 28 } })
  }

  numbersRequestCount += 1
  if (numbersRequestCount === 1) return Response.json({ status: 'success', numbers: ['11111111'] })
  if (numbersRequestCount === 2) {
    return new Promise((resolve, reject) => {
      resolveOldNumbers = () => resolve(Response.json({ status: 'success', numbers: ['99999999'] }))
      init?.signal?.addEventListener(
        'abort',
        () => {
          oldNumbersAborted = true
          reject(new DOMException('Aborted', 'AbortError'))
        },
        { once: true },
      )
    })
  }
  if (numbersRequestCount === 3) return Response.json({ status: 'success', numbers: ['22222222'] })
  return new Promise((_, reject) => {
    init?.signal?.addEventListener(
      'abort',
      () => {
        autoRequestAborted = true
        reject(new DOMException('Aborted', 'AbortError'))
      },
      { once: true },
    )
  })
}

type Scope = { readonly accountId: string; readonly subscriptionId: string }

export function Harness(): JSX.Element {
  const [scope, setScope] = useState<Scope>({ accountId: 'account-1', subscriptionId: 'subscription-1' })
  const cmn = useCmn(scope.accountId, scope.subscriptionId, true)
  const cmnRef = useRef(cmn)
  const scenarioStartedRef = useRef(false)

  useLayoutEffect(() => {
    cmnRef.current = cmn
  }, [cmn])

  useEffect(() => {
    if (scenarioStartedRef.current) return
    scenarioStartedRef.current = true

    void (async () => {
      const oldEligibility = cmnRef.current.checkCmnEligibility()
      await cmnRef.current.refreshCmnNumbers(() => undefined)
      cmnRef.current.setSelectedNumber('11111111')
      clockOffset += 3000
      await wait(300)

      const oldNumbers = cmnRef.current.refreshCmnNumbers(() => undefined)
      await wait(0)
      const harness = (): HTMLElement => document.getElementById('scope-harness') as HTMLElement
      const manualCleared = harness().dataset.numbers === '' && harness().dataset.numbersLoading === 'true'
      const overlapOutcome = await cmnRef.current.refreshCmnNumbers(() => undefined)
      const nonOverlap = overlapOutcome.kind === 'unavailable' && numbersRequestCount === 2

      setScope({ accountId: 'account-2', subscriptionId: 'subscription-2' })
      await wait(0)
      await wait(0)
      const scopeReset =
        harness().dataset.numbers === '' &&
        harness().dataset.numbersLoading === 'false' &&
        harness().dataset.selected === ''

      resolveOldEligibility?.()
      resolveOldNumbers?.()
      await Promise.all([oldEligibility, oldNumbers])
      await wait(0)
      const staleIgnored = harness().dataset.offer === '' && harness().dataset.numbers === ''

      await cmnRef.current.checkCmnEligibility()
      const newNumbers = await cmnRef.current.refreshCmnNumbers(() => undefined)
      await wait(0)
      const newScopeApplied =
        newNumbers.kind === 'success' &&
        harness().dataset.offer === 'new-offer' &&
        harness().dataset.numbers === '22222222'
      const exactCooldown = harness().dataset.cooldown === '3' && harness().dataset.canRefresh === 'false'

      clockOffset += 3000
      await wait(300)
      const cooldownReenabled = harness().dataset.cooldown === '0' && harness().dataset.canRefresh === 'true'

      cmnRef.current.changeCmnPattern('666')
      await wait(0)
      cmnRef.current.startCmnAutoRefresh(() => undefined)
      await wait(0)
      const autoLoading = harness().dataset.numbersLoading === 'true'
      cmnRef.current.cancelCmnAutoRefresh()
      await wait(0)
      const cancelReset =
        harness().dataset.numbersLoading === 'false' && harness().dataset.autoMessage === '已取消自动查找'

      const target = harness()
      target.setAttribute('data-manual-cleared', String(manualCleared))
      target.setAttribute('data-non-overlap', String(nonOverlap))
      target.setAttribute('data-scope-reset', String(scopeReset))
      target.setAttribute('data-old-eligibility-aborted', String(oldEligibilityAborted))
      target.setAttribute('data-old-numbers-aborted', String(oldNumbersAborted))
      target.setAttribute('data-stale-ignored', String(staleIgnored))
      target.setAttribute('data-new-scope-applied', String(newScopeApplied))
      target.setAttribute('data-exact-cooldown', String(exactCooldown))
      target.setAttribute('data-cooldown-reenabled', String(cooldownReenabled))
      target.setAttribute('data-auto-loading', String(autoLoading))
      target.setAttribute('data-auto-request-aborted', String(autoRequestAborted))
      target.setAttribute('data-cancel-reset', String(cancelReset))
      target.setAttribute('data-request-urls', requestUrls.join('|'))
      target.setAttribute('data-complete', 'true')
    })()
  }, [])

  return (
    <main
      id="scope-harness"
      data-auto-message={cmn.cmnAutoRefresh.message}
      data-can-refresh={cmn.cmnCanRefresh}
      data-cooldown={cmn.cmnCooldown}
      data-numbers={cmn.cmnNumbers.join(',')}
      data-numbers-loading={cmn.cmnNumbersLoading}
      data-offer={cmn.cmnData?.offerId ?? ''}
      data-selected={cmn.selectedNumber ?? ''}
    >
      CMN scope harness
    </main>
  )
}

createRoot(document.getElementById('root') as HTMLElement).render(<Harness />)

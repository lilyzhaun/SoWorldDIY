import { StrictMode, useEffect, useLayoutEffect, useRef } from 'react'
import { createRoot } from 'react-dom/client'

import { useCmn } from '@/hooks/useCmn'

const wait = (milliseconds: number): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, milliseconds))
const realDateNow = Date.now.bind(Date)
let clockOffset = 0
let numbersRequest = 0
Date.now = (): number => realDateNow() + clockOffset

window.fetch = async (input, init): Promise<Response> => {
  const url = String(input)
  if (url.includes('/api/cmn/check')) {
    await Promise.resolve()
    return Response.json({ status: 'success', data: { offerId: 'offer-1', offerSubType: 'CMN', price: 28 } })
  }

  numbersRequest += 1
  if (numbersRequest === 2) {
    return new Promise((_, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
    })
  }
  return Response.json({ status: 'success', numbers: numbersRequest === 1 ? ['11111111'] : ['12345678'] })
}

export function Harness(): JSX.Element {
  const cmn = useCmn('account-1', 'subscription-1', true)
  const checkCmnEligibility = cmn.checkCmnEligibility
  const cmnRef = useRef(cmn)
  const scenarioStartedRef = useRef(false)

  useLayoutEffect(() => {
    cmnRef.current = cmn
  }, [cmn])

  useEffect(() => {
    void checkCmnEligibility()
  }, [checkCmnEligibility])

  useEffect(() => {
    if (!cmn.cmnData || scenarioStartedRef.current) return
    scenarioStartedRef.current = true

    void (async () => {
      const eligibilityApplied = cmn.cmnData !== null
      const manualOutcome = await cmn.refreshCmnNumbers(() => undefined)
      await wait(0)
      const getHarness = (): HTMLElement => document.getElementById('hook-harness') as HTMLElement
      const numbersApplied = manualOutcome.kind === 'success' && getHarness().dataset.numbers === '11111111'

      clockOffset += 3000
      await wait(300)
      cmnRef.current.changeCmnPattern('666')
      await wait(0)

      cmnRef.current.startCmnAutoRefresh(() => undefined)
      await wait(0)
      cmnRef.current.cancelCmnAutoRefresh()
      await wait(0)
      const firstRequestCancelRestored =
        getHarness().dataset.canRefresh === 'true' && getHarness().dataset.cooldown === '0'

      cmnRef.current.startCmnAutoRefresh(() => undefined)
      await wait(20)
      const cooldownBeforeCancel = getHarness().dataset.cooldown
      cmnRef.current.cancelCmnAutoRefresh()
      await wait(0)
      const cooldownAfterCancel = getHarness().dataset.cooldown
      const cooldownPreserved =
        cooldownBeforeCancel === cooldownAfterCancel &&
        cooldownAfterCancel !== '0' &&
        getHarness().dataset.canRefresh === 'false'

      clockOffset += 3000
      await wait(300)
      const cooldownReenabled = getHarness().dataset.cooldown === '0' && getHarness().dataset.canRefresh === 'true'

      const harness = getHarness()
      harness.setAttribute('data-strict-eligibility-applied', String(eligibilityApplied))
      harness.setAttribute('data-strict-numbers-applied', String(numbersApplied))
      harness.setAttribute('data-first-request-cancel-restored', String(firstRequestCancelRestored))
      harness.setAttribute('data-cooldown-preserved', String(cooldownPreserved))
      harness.setAttribute('data-cooldown-reenabled', String(cooldownReenabled))
      harness.setAttribute('data-complete', 'true')
    })()
  }, [cmn])

  return (
    <main
      id="hook-harness"
      data-can-refresh={cmn.cmnCanRefresh}
      data-cooldown={cmn.cmnCooldown}
      data-data-ready={cmn.cmnData !== null}
      data-numbers={cmn.cmnNumbers.join(',')}
    >
      StrictMode CMN hook harness
    </main>
  )
}

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>
    <Harness />
  </StrictMode>,
)

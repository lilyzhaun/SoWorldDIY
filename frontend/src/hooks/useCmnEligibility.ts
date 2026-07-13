import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react'

import { apiGet } from '@/api/client'
import type { CmnCheckResponse } from '@/types'
import { toUserFacingApiError } from '@/utils'
import { getApiUrl } from '@/utils/mainPage'

type CmnLifecycle = {
  readonly mountedRef: MutableRefObject<boolean>
  readonly scopeGenerationRef: MutableRefObject<number>
}

type CmnEligibilityOptions = {
  readonly accountId: string
  readonly cancelCmnAutoRefresh: (announce?: boolean) => void
  readonly currentSubId: string
  readonly lifecycle: CmnLifecycle
}

export function useCmnEligibility({ accountId, cancelCmnAutoRefresh, currentSubId, lifecycle }: CmnEligibilityOptions) {
  const { mountedRef, scopeGenerationRef } = lifecycle
  const [cmnLoading, setCmnLoading] = useState(false)
  const [cmnError, setCmnError] = useState('')
  const [cmnData, setCmnData] = useState<CmnCheckResponse['data'] | null>(null)
  const eligibilityAbortRef = useRef<AbortController | null>(null)

  useEffect(() => () => eligibilityAbortRef.current?.abort(), [])

  useEffect(() => {
    eligibilityAbortRef.current?.abort()
    setCmnLoading(false)
    setCmnData(null)
    setCmnError('')
  }, [accountId, currentSubId])

  const checkCmnEligibility = useCallback(async (): Promise<void> => {
    if (!currentSubId) return
    eligibilityAbortRef.current?.abort()
    const controller = new AbortController()
    eligibilityAbortRef.current = controller
    const scope = scopeGenerationRef.current
    setCmnLoading(true)
    setCmnError('')
    try {
      const url = getApiUrl(`/api/cmn/check?subscriptionId=${currentSubId}`, accountId)
      const data = await apiGet<CmnCheckResponse>(url, { signal: controller.signal })
      if (!mountedRef.current || controller.signal.aborted || scope !== scopeGenerationRef.current) return
      if (data.status === 'success' && data.data) {
        setCmnData(data.data)
      } else {
        setCmnData(null)
        setCmnError(data.message || '无法使用换号服务')
        cancelCmnAutoRefresh(false)
      }
    } catch (error: unknown) {
      if (controller.signal.aborted) return
      if (mountedRef.current && scope === scopeGenerationRef.current) {
        setCmnData(null)
        setCmnError(toUserFacingApiError(error, '网络错误'))
        cancelCmnAutoRefresh(false)
      }
    } finally {
      if (mountedRef.current && !controller.signal.aborted && scope === scopeGenerationRef.current) setCmnLoading(false)
    }
  }, [accountId, cancelCmnAutoRefresh, currentSubId, mountedRef, scopeGenerationRef])

  return { checkCmnEligibility, cmnData, cmnError, cmnLoading }
}

import { useRef, useState } from 'react'

import { ApiHttpError, apiPostJson, newOperationId } from '@/api/client'
import type { Subscription, TransferDraft } from '@/types'
import { toUserFacingApiError } from '@/utils'
import { getApiUrl } from '@/utils/mainPage'

export function useTransfer(accountId: string, currentSubId: string) {
  const [transferDraft, setTransferDraft] = useState<TransferDraft | null>(null)
  const [transferTarget, setTransferTarget] = useState('')
  const [transferAmount, setTransferAmount] = useState('')
  const [transferError, setTransferError] = useState('')
  const [transferSubmitting, setTransferSubmitting] = useState(false)
  const requestId = useRef('')
  const inFlight = useRef(false)

  const openTransferModal = (event: React.MouseEvent, draft: TransferDraft, openModal: () => void): void => {
    event.stopPropagation()
    requestId.current = ''
    setTransferDraft(draft)
    setTransferTarget('')
    setTransferAmount('')
    setTransferError('')
    openModal()
  }

  const resetTransfer = (): void => {
    setTransferError('')
    setTransferSubmitting(false)
  }

  const submitTransfer = async (currentSub: Subscription | null): Promise<string | null> => {
    if (!transferDraft || !currentSub || inFlight.current) return null
    const target = transferTarget.trim()
    const amount = Number.parseFloat(transferAmount)
    if (!target || target.length < 8) {
      setTransferError('请输入有效的手机号码')
      return null
    }
    if (!amount || Number.isNaN(amount)) {
      setTransferError('请输入转移数量')
      return null
    }
    if (amount < transferDraft.minTransfer) {
      setTransferError(`转移数量不能少于 ${transferDraft.minTransfer}`)
      return null
    }
    if (amount > transferDraft.maxValue) {
      setTransferError('余额不足')
      return null
    }
    inFlight.current = true
    requestId.current ||= newOperationId()
    setTransferSubmitting(true)
    setTransferError('')
    try {
      const url = getApiUrl('/api/sim/transfer', accountId)
      const data = await apiPostJson<{ status?: string; message?: string }>(
        url,
        {
          subscriptionId: currentSubId,
          sourceMsisdn: currentSub.mobile,
          targetMsisdn: target,
          amount,
          userOfferId: transferDraft.userOfferId,
          balanceResourceId: transferDraft.balanceResourceId,
          unit: transferDraft.unit,
          productFamily: transferDraft.productFamily,
          account_id: accountId,
        },
        { headers: { 'Idempotency-Key': requestId.current } },
      )
      if (data.status === 'success') {
        return target
      } else {
        setTransferSubmitting(false)
        setTransferError(data.message || '转移失败')
      }
    } catch (error: unknown) {
      if (error instanceof ApiHttpError && error.status === 400) requestId.current = ''
      setTransferSubmitting(false)
      setTransferError(
        error instanceof ApiHttpError
          ? toUserFacingApiError(error, '转移失败')
          : '操作结果待确认，请先核对资源余额；不要再次发起转移',
      )
    } finally {
      inFlight.current = false
    }
    return null
  }

  return {
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
  }
}

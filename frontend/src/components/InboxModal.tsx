import { useEffect, useMemo, useRef } from 'react'

import { useDialogAccessibility } from '@/hooks/useDialogAccessibility'
import type { InboxMessage, Subscription } from '@/types'
import { sanitizeInboxContent } from '@/utils/sanitizeInboxContent'
import { UiIcon } from './UiIcon'

type InboxModalProps = {
  readonly activeInboxIndex: number | null
  readonly inboxLoading: boolean
  readonly inboxMessages: InboxMessage[]
  readonly inboxOpen: boolean
  readonly onClose: () => void
  readonly onRefresh: () => void
  readonly onSelectMessage: (index: number | null) => void
  readonly subscriptions: Subscription[]
}

function formatInboxDate(value: string): string {
  return value.replace('T', ' ').split('+')[0].slice(0, 16)
}

export function InboxModal({
  activeInboxIndex,
  inboxLoading,
  inboxMessages,
  inboxOpen,
  onClose,
  onRefresh,
  onSelectMessage,
  subscriptions,
}: InboxModalProps): JSX.Element {
  const activeMessage = activeInboxIndex === null ? null : (inboxMessages[activeInboxIndex] ?? null)
  const safeActiveInboxContent = useMemo(
    () => sanitizeInboxContent(activeMessage?.content ?? ''),
    [activeMessage?.content],
  )
  const dialogRef = useDialogAccessibility(inboxOpen, onClose)
  const backButtonRef = useRef<HTMLButtonElement>(null)
  const rowRefs = useRef<Array<HTMLButtonElement | null>>([])
  const previousIndexRef = useRef<number | null>(null)

  useEffect(() => {
    const previousIndex = previousIndexRef.current
    previousIndexRef.current = activeInboxIndex
    if (activeInboxIndex !== null) backButtonRef.current?.focus()
    else if (previousIndex !== null) rowRefs.current[previousIndex]?.focus()
  }, [activeInboxIndex])

  return (
    <div
      ref={dialogRef}
      id="inboxModal"
      className={`modal-overlay records-modal-overlay ${inboxOpen ? 'show' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="inboxModalTitle"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className="modal-box records-modal-box">
        {activeMessage ? (
          <>
            <header className="records-modal-header records-detail-header">
              <button
                ref={backButtonRef}
                type="button"
                className="records-back-btn"
                aria-label="返回收件箱"
                onClick={() => onSelectMessage(null)}
              >
                <UiIcon name="arrow-left" size={18} />
              </button>
              <div className="records-header-copy">
                <h2 className="records-modal-title records-detail-title" id="inboxModalTitle">
                  {activeMessage.subject}
                </h2>
                <p className="records-modal-subtitle">{formatInboxDate(activeMessage.post_dt)}</p>
              </div>
              <button type="button" className="modal-icon-btn" aria-label="关闭收件箱" onClick={onClose}>
                <UiIcon name="close" />
              </button>
            </header>
            <div id="inboxContent" className="records-modal-content records-detail-content">
              <div className="records-detail-meta">
                <span>
                  <UiIcon name="phone" size={16} />
                  {subscriptions.find((item) => item.subscriptionId === activeMessage.intended_subscription_id)
                    ?.mobile ?? activeMessage.intended_subscription_id}
                </span>
                <time>{formatInboxDate(activeMessage.post_dt)}</time>
              </div>
              <div
                className="inbox-detail records-detail-surface"
                dangerouslySetInnerHTML={{ __html: safeActiveInboxContent }}
              />
            </div>
          </>
        ) : (
          <>
            <header className="records-modal-header">
              <div className="records-header-copy">
                <h2 className="records-modal-title" id="inboxModalTitle">
                  收件箱
                </h2>
                <p className="records-modal-subtitle">共 {inboxMessages.length} 条消息</p>
              </div>
              <div className="modal-header-actions">
                <button
                  id="inboxRefresh"
                  type="button"
                  className="modal-icon-btn"
                  aria-label="刷新收件箱"
                  onClick={onRefresh}
                >
                  <UiIcon name="refresh" size={18} />
                </button>
                <button
                  type="button"
                  className="modal-icon-btn"
                  data-dialog-initial-focus
                  aria-label="关闭收件箱"
                  onClick={onClose}
                >
                  <UiIcon name="close" />
                </button>
              </div>
            </header>
            <div id="inboxContent" className="records-modal-content">
              {inboxLoading ? (
                <div className="records-state loader">加载中…</div>
              ) : inboxMessages.length === 0 ? (
                <div className="records-state empty-state">暂无消息</div>
              ) : (
                <ul className="records-list">
                  {inboxMessages.map((message, index) => {
                    const mobile =
                      subscriptions.find((item) => item.subscriptionId === message.intended_subscription_id)?.mobile ??
                      message.intended_subscription_id
                    return (
                      <li key={`${message.subject}-${index}`} className="records-list-item">
                        <button
                          ref={(element) => {
                            rowRefs.current[index] = element
                          }}
                          type="button"
                          className="records-row"
                          onClick={() => onSelectMessage(index)}
                        >
                          <span className="records-row-copy">
                            <span className="records-row-title">{message.subject}</span>
                            <span className="records-row-meta">
                              <span>
                                <UiIcon name="phone" size={16} />
                                {mobile}
                              </span>
                              <time>{formatInboxDate(message.post_dt)}</time>
                            </span>
                          </span>
                          <UiIcon className="records-row-chevron" name="chevron-right" size={18} />
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

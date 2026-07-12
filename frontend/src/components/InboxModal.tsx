import { useMemo } from 'react'
import DOMPurify from 'dompurify'

import type { InboxMessage, Subscription } from '../types'
import { useDialogAccessibility } from '../hooks/useDialogAccessibility'
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
  const activeInboxContent = activeInboxIndex !== null ? inboxMessages[activeInboxIndex]?.content || '' : ''
  const safeActiveInboxContent = useMemo(() => DOMPurify.sanitize(activeInboxContent), [activeInboxContent])
  const dialogRef = useDialogAccessibility(inboxOpen, onClose)

  return (
    <div ref={dialogRef} id="inboxModal" className={`modal-overlay ${inboxOpen ? 'show' : ''}`} role="dialog" aria-modal="true" aria-labelledby="inboxModalTitle" onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div className="modal-box" style={{ maxWidth: '400px', padding: '20px 0', height: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '0 20px 15px 20px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <div className="modal-title" id="inboxModalTitle" style={{ margin: 0 }}>收件箱</div>
          <div className="modal-header-actions">
            <button id="inboxRefresh" type="button" className="modal-icon-btn" aria-label="刷新收件箱" onClick={onRefresh}><UiIcon name="refresh" size={18} /></button>
            <button type="button" className="modal-icon-btn" data-dialog-initial-focus aria-label="关闭收件箱" onClick={onClose}><UiIcon name="close" /></button>
          </div>
        </div>
        <div id="inboxContent" style={{ padding: 0, flex: 1, overflowY: 'auto' }}>
          {inboxLoading ? <div className="loader" style={{ padding: '20px' }}>加载中…</div> : activeInboxIndex === null ? (
            inboxMessages.length === 0 ? <div className="empty-state">暂无消息</div> : <div className="inbox-list-container">{inboxMessages.map((msg, index) => {
              const dateStr = (msg.post_dt || '').replace('T', ' ').split('+')[0].slice(0, 16)
              const mobile = subscriptions.find((item) => item.subscriptionId === msg.intended_subscription_id)?.mobile || msg.intended_subscription_id
              return <div key={`${msg.subject}-${index}`} className="inbox-item" role="button" tabIndex={0} onClick={() => onSelectMessage(index)} onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onSelectMessage(index) } }}><div className="inbox-subject">{msg.subject}</div><div className="inbox-meta"><span><UiIcon name="phone" size={16} /> {mobile}</span><span>{dateStr}</span></div></div>
            })}</div>
          ) : (
            <div style={{ padding: 0 }}>
              <button type="button" className="inbox-back-header" onClick={() => onSelectMessage(null)}><UiIcon name="arrow-left" size={16} /> <span>返回</span></button>
              <div style={{ padding: '0 20px' }}>
                <div style={{ marginBottom: '15px' }}><div style={{ fontSize: '16px', fontWeight: 700, marginBottom: '5px' }}>{inboxMessages[activeInboxIndex]?.subject}</div><div style={{ fontSize: '12px', color: '#94a3b8' }}>{(inboxMessages[activeInboxIndex]?.post_dt || '').replace('T', ' ').split('+')[0]}</div></div>
                <div className="inbox-detail" dangerouslySetInnerHTML={{ __html: safeActiveInboxContent }}></div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

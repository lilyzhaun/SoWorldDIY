import type { AvailableAccount, Subscription } from '../types'

type AccountSwitchModalContentProps = {
  readonly availableAccounts: AvailableAccount[]
  readonly currentSubId: string
  readonly onAddAccount: () => void
  readonly onSwitchAccount: (identifier: string) => void
  readonly onSwitchSubscription: (subscription: Subscription) => void
  readonly subscriptions: Subscription[]
}

export function AccountSwitchModalContent({ availableAccounts, currentSubId, onAddAccount, onSwitchAccount, onSwitchSubscription, subscriptions }: AccountSwitchModalContentProps): JSX.Element {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '10px' }}>
      {subscriptions.length > 0 ? <div><div style={{ fontSize: '13px', color: 'var(--text-sub)', marginBottom: '10px', fontWeight: 600 }}>当前账号号码</div><div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>{subscriptions.map((subscription) => {
        const isCurrent = subscription.subscriptionId === currentSubId
        const statusIcon = subscription.status === 'ACTIVE' ? '🟢' : subscription.status === 'PREACTIVE' ? '🟠' : subscription.status === 'SUSPENDED' ? '🔴' : '⚪'
        return <div key={subscription.subscriptionId} onClick={() => onSwitchSubscription(subscription)} style={{ padding: '14px', borderRadius: '16px', cursor: 'pointer', position: 'relative', transition: '0.2s', background: isCurrent ? 'rgba(255, 123, 0, 0.05)' : 'var(--bg-card)', border: isCurrent ? '1.5px solid var(--primary)' : '1px solid var(--border-color)' }}><div style={{ fontSize: '17px', fontWeight: 700, display: 'flex', justifyContent: 'space-between', color: isCurrent ? 'var(--primary)' : 'var(--text-main)' }}><span>📱 {subscription.mobile}</span>{isCurrent ? <span>✔</span> : null}</div><div style={{ fontSize: '12px', color: 'var(--text-sub)', marginTop: '6px', display: 'flex', justifyContent: 'space-between' }}><span>{statusIcon} {subscription.brand || '3HK'}</span><span style={{ fontFamily: 'monospace' }}>..{(subscription.iccid || '').slice(-4)}</span></div></div>
      })}</div></div> : null}
      {availableAccounts.length > 0 ? <div><div style={{ fontSize: '13px', color: 'var(--text-sub)', marginBottom: '10px', fontWeight: 600 }}>切换其他账号</div><div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>{availableAccounts.map((account) => <div key={account.identifier} onClick={() => { if (!account.active) onSwitchAccount(account.identifier) }} style={{ padding: '12px 14px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', border: '1px solid var(--border-color)', cursor: account.active ? 'default' : 'pointer', background: account.active ? 'var(--bg-secondary)' : 'var(--bg-card)', opacity: account.active ? 0.6 : 1 }}><div style={{ display: 'flex', flexDirection: 'column' }}><div style={{ fontSize: '14px', fontWeight: 600 }}>👤 {account.identifier}</div><div style={{ fontSize: '11px', color: 'var(--text-sub)' }}>{account.subBrand}</div></div>{account.active ? <span style={{ fontSize: '10px', padding: '2px 8px', background: 'var(--border-color)', borderRadius: '6px' }}>当前</span> : <span style={{ color: 'var(--text-sub)', fontSize: '18px' }}>›</span>}</div>)}</div></div> : null}
      <button onClick={onAddAccount} style={{ width: '100%', padding: '14px', background: 'var(--bg-secondary)', border: '1px dashed var(--border-color)', color: 'var(--text-sub)', borderRadius: '14px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginTop: '8px' }}><span style={{ fontSize: '18px' }}>+</span> 添加账号</button>
    </div>
  )
}

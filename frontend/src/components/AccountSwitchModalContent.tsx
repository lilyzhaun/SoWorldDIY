import type { AvailableAccount, Subscription } from '@/types'
import { UiIcon } from './UiIcon'

type AccountSwitchModalContentProps = {
  readonly availableAccounts: AvailableAccount[]
  readonly currentSubId: string
  readonly onAddAccount: () => void
  readonly onSwitchAccount: (identifier: string) => void
  readonly onSwitchSubscription: (subscription: Subscription) => void
  readonly subscriptions: Subscription[]
}

export function AccountSwitchModalContent({
  availableAccounts,
  currentSubId,
  onAddAccount,
  onSwitchAccount,
  onSwitchSubscription,
  subscriptions,
}: AccountSwitchModalContentProps): React.JSX.Element {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '10px' }}>
      {subscriptions.length > 0 ? (
        <div>
          <div style={{ fontSize: '13px', color: 'var(--text-sub)', marginBottom: '10px', fontWeight: 600 }}>
            当前账号号码
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {subscriptions.map((subscription) => {
              const isCurrent = subscription.subscriptionId === currentSubId
              const statusTone =
                subscription.status === 'ACTIVE'
                  ? 'active'
                  : subscription.status === 'PREACTIVE'
                    ? 'preactive'
                    : subscription.status === 'SUSPENDED'
                      ? 'suspended'
                      : 'unknown'
              return (
                <button
                  type="button"
                  key={subscription.subscriptionId}
                  aria-label={`切换至号码 ${subscription.mobile}`}
                  className={`account-switch-option${isCurrent ? ' current' : ''}`}
                  onClick={() => onSwitchSubscription(subscription)}
                >
                  <span className="account-switch-primary">
                    <span>
                      <UiIcon name="phone" size={16} /> {subscription.mobile}
                    </span>
                    {isCurrent ? <UiIcon name="check" size={16} /> : null}
                  </span>
                  <span className="account-switch-meta">
                    <span>
                      <UiIcon name="circle" size={16} className={`account-status-circle tone-${statusTone}`} />{' '}
                      {subscription.status} · {subscription.brand || '3HK'}
                    </span>
                    <span className="account-switch-iccid">..{(subscription.iccid || '').slice(-4)}</span>
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      ) : null}
      {availableAccounts.length > 0 ? (
        <div>
          <div style={{ fontSize: '13px', color: 'var(--text-sub)', marginBottom: '10px', fontWeight: 600 }}>
            切换其他账号
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {availableAccounts.map((account) => (
              <button
                type="button"
                className="account-switch-account"
                key={account.identifier}
                disabled={account.active}
                onClick={() => onSwitchAccount(account.identifier)}
              >
                <span>
                  <span className="account-switch-identifier">
                    <UiIcon name="user" size={16} /> {account.identifier}
                  </span>
                  <span className="account-switch-brand">{account.subBrand}</span>
                </span>
                {account.active ? (
                  <span className="account-switch-current">当前</span>
                ) : (
                  <UiIcon name="chevron-right" size={18} />
                )}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <button type="button" className="account-add-button" onClick={onAddAccount}>
        <UiIcon name="plus" size={18} /> 添加账号
      </button>
    </div>
  )
}

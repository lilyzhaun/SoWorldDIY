import type { AvailableAccount, Category, Subscription } from '@/types'
import { formatStatus } from '@/utils/mainPage'
import { UiIcon } from './UiIcon'

type MainHeaderProps = {
  readonly availableAccounts: AvailableAccount[]
  readonly balance: string
  readonly category: Category
  readonly currentSub: Subscription | null
  readonly noNumberMode: boolean
  readonly onLogout: () => void
  readonly onOpenHistory: () => void
  readonly onOpenInbox: () => void
  readonly onOpenSwitch: () => void
  readonly onSearchChange: (value: string) => void
  readonly onShowAlert: (text: string) => void
  readonly onSwitchCategory: (category: Category) => void
  readonly search: string
}

export function MainHeader({
  availableAccounts,
  balance,
  category,
  currentSub,
  noNumberMode,
  onLogout,
  onOpenHistory,
  onOpenInbox,
  onOpenSwitch,
  onSearchChange,
  onShowAlert,
  onSwitchCategory,
  search,
}: MainHeaderProps): JSX.Element {
  return (
    <div className="fixed-header-wrapper">
      <div className="container" style={{ paddingBottom: 0 }}>
        <div className="mini-user-card">
          <div className="user-main">
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span id="u_mobile">{noNumberMode ? '无号码账号' : currentSub?.mobile || '加载中…'}</span>
              <button
                type="button"
                id="u_switch_hint"
                style={{ display: availableAccounts.length > 0 ? 'inline-flex' : 'none' }}
                onClick={onOpenSwitch}
              >
                <UiIcon className="switch-hint-icon" name="chevron-down" size={16} /> 切换
              </button>
            </h2>
            <div
              style={{
                fontSize: '24px',
                fontWeight: 800,
                color: 'var(--text-main)',
                margin: '5px 0 2px 0',
                display: noNumberMode ? 'none' : 'flex',
                alignItems: 'center',
              }}
            >
              <span style={{ fontSize: '14px', color: 'var(--text-sub)', fontWeight: 600, marginRight: '2px' }}>$</span>
              <span id="u_balance">{balance}</span>
              <button
                className="topup-mini-btn"
                onClick={() =>
                  currentSub?.mobile
                    ? window.open(`https://www.three.com.hk/prepaid/account/tc/topup/${currentSub.mobile}`, '_blank')
                    : onShowAlert('无法获取当前手机号')
                }
              >
                充值
              </button>
            </div>
            <div className="user-sub" id="u_dates_container" style={{ display: noNumberMode ? 'none' : undefined }}>
              {currentSub?.activationDate ? <span>{currentSub.activationDate} 激活</span> : null}
              {currentSub?.activationDate && currentSub?.subsEndDate ? ' · ' : null}
              {currentSub?.subsEndDate ? <span>{currentSub.subsEndDate} 到期</span> : null}
            </div>
            <div
              className="user-sub"
              style={{ marginTop: '4px', fontSize: '11px', opacity: 0.85, display: noNumberMode ? 'none' : undefined }}
            >
              <span id="u_status_badge" style={{ fontWeight: 700, color: formatStatus(currentSub?.status).color }}>
                {formatStatus(currentSub?.status).text}
              </span>{' '}
              · ICCID: <span id="u_iccid">{currentSub?.iccid || '--'}</span>
            </div>
          </div>
          <div className="user-actions" style={{ display: noNumberMode ? 'none' : undefined }}>
            <button className="icon-btn" aria-label="交易记录" onClick={onOpenHistory}>
              <svg className="icon">
                <use xlinkHref="#icon-history"></use>
              </svg>
            </button>
            <button className="icon-btn" aria-label="收件箱" onClick={onOpenInbox}>
              <svg className="icon">
                <use xlinkHref="#icon-mail"></use>
              </svg>
            </button>
            <button type="button" onClick={onLogout} className="logout-btn-icon" aria-label="退出登录">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                <path d="M16 13v-2H7V8l-5 4 5 4v-3z"></path>
                <path d="M20 3h-9c-1.103 0-2 .897-2 2v4h2V5h9v14h-9v-4H9v4c0 1.103.897 2 2 2h9c1.103 0 2-.897 2-2V5c0-1.103-.897-2-2-2z"></path>
              </svg>
            </button>
          </div>
        </div>

        <div className="toolbar">
          <div
            className="search-box"
            id="searchBoxContainer"
            style={{ display: category === 'CMN' || category === 'SUBSCRIBED' ? 'none' : undefined }}
          >
            <input
              type="text"
              id="searchInput"
              placeholder="搜索套餐..."
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
            />
          </div>
          <div className="category-tabs">
            {(noNumberMode
              ? (['ALL', 'LOCAL', 'TRAVEL', 'OTHER'] as Category[])
              : (['ALL', 'LOCAL', 'TRAVEL', 'SUBSCRIBED', 'OTHER', 'CMN'] as Category[])
            ).map((item) => (
              <button
                type="button"
                key={item}
                className={`cat-tab ${category === item ? 'active' : ''}`}
                style={item === 'CMN' ? { color: '#e53e3e' } : undefined}
                onClick={() => onSwitchCategory(item)}
              >
                {item === 'ALL'
                  ? '全部'
                  : item === 'LOCAL'
                    ? '本地'
                    : item === 'TRAVEL'
                      ? '外遊'
                      : item === 'SUBSCRIBED'
                        ? '已订购'
                        : item === 'OTHER'
                          ? '其他'
                          : '更换号码'}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

import type { Subscription, TransferDraft } from '@/types'
import { normalizeUnit, stripHtml } from '@/utils/mainPage'
import { UiIcon } from './UiIcon'

type ActiveOffersSectionProps = {
  readonly currentSub: Subscription | null
  readonly onOpenTransfer: (event: React.MouseEvent, draft: TransferDraft) => void
  readonly onRefresh: () => void
  readonly onSelectOffer: (planId: string | null) => void
  readonly refreshingUsage: boolean
  readonly selectedPlanId: string | null
  readonly visible: boolean
}

export function ActiveOffersSection({
  currentSub,
  onOpenTransfer,
  onRefresh,
  onSelectOffer,
  refreshingUsage,
  selectedPlanId,
  visible,
}: ActiveOffersSectionProps): JSX.Element {
  const activeOffers = currentSub?.activeOffers || []
  return (
    <div id="activeOffersContainer" style={{ display: visible ? 'block' : 'none' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginTop: '-10px',
          paddingBottom: '10px',
          paddingRight: '5px',
        }}
      >
        <button id="refreshUsageBtn" className="refresh-text-btn" disabled={refreshingUsage} onClick={onRefresh}>
          <UiIcon className="refresh-text-icon" name="refresh" /> {refreshingUsage ? '同步中…' : '刷新用量'}
        </button>
      </div>
      <div id="activeOffersList" className="plan-list">
        {activeOffers.map((offer) => {
          const isOpen = selectedPlanId === `sub-${offer.offerId}`
          let status = offer.planStatus || ''
          let statusColor = '#64748b'
          let statusBackground = '#f1f5f9'
          if (status === 'ACTIVE') {
            status = '生效中'
            statusColor = '#059669'
            statusBackground = '#d1fae5'
          } else if (status === 'PREACTIVE') {
            status = '待生效'
            statusColor = '#d97706'
            statusBackground = '#fef3c7'
          }
          return (
            <div key={offer.offerId} className={`plan-card ${isOpen ? 'open' : ''}`}>
              {offer.isVoWifi ? <div className="tag-vowifi">VoWiFi</div> : null}
              <button
                type="button"
                className="plan-card-disclosure"
                aria-expanded={isOpen}
                aria-controls={`active-offer-details-${offer.offerId}`}
                onClick={() => onSelectOffer(isOpen ? null : `sub-${offer.offerId}`)}
              >
                <div className="card-header">
                  <div className="plan-name">{offer.name}</div>
                  <div className="plan-price">{offer.price ? `$${offer.price}` : ''}</div>
                </div>
                <div className="card-meta">
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span
                      style={{
                        background: statusBackground,
                        color: statusColor,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontWeight: 700,
                        marginRight: '6px',
                      }}
                    >
                      {status || '--'}
                    </span>
                    <span className="validity-badge" style={{ background: '#e0f2fe', color: '#0369a1' }}>
                      有效期至 {offer.endDate}
                    </span>
                  </div>
                  <UiIcon className={`arrow ${isOpen ? 'open' : ''}`} name="chevron-down" />
                </div>
              </button>
              <div
                id={`active-offer-details-${offer.offerId}`}
                className={`card-details ${isOpen ? 'open' : ''}`}
                aria-hidden={!isOpen}
                inert={isOpen ? undefined : ''}
              >
                <div className="card-details-inner">
                  {offer.usage && offer.usage.length > 0 ? (
                    <div className="usage-section">
                      {offer.usage.map((usage, index) => {
                        const unit = (usage.unit || '').toLowerCase()
                        let totalLabel = `${Math.floor(usage.total || 0)}${normalizeUnit(usage.unit)}`
                        let remainLabel = `${Math.floor(usage.remain || 0)}${normalizeUnit(usage.unit)}`
                        if (unit === 'megabytes') {
                          const total = usage.total || 0
                          const remain = usage.remain || 0
                          totalLabel = total > 1024 ? `${(total / 1024).toFixed(1)}GB` : `${Math.floor(total)}MB`
                          remainLabel = remain > 1024 ? `${(remain / 1024).toFixed(1)}GB` : `${Math.floor(remain)}MB`
                        }
                        const percent = usage.percent || 0
                        const barClass = `usage-bar ${percent < 20 ? 'critical' : percent < 50 ? 'low' : ''}`.trim()
                        return (
                          <div key={`${offer.offerId}-${index}`} className="usage-item">
                            <div className="usage-header">
                              <span>{usage.name || '数据'}</span>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                                <span>
                                  剩 {remainLabel} / 总 {totalLabel}
                                </span>
                                {usage.canTransfer ? (
                                  <button
                                    className="trans-btn"
                                    onClick={(event) =>
                                      onOpenTransfer(event, {
                                        userOfferId: offer.offerId,
                                        balanceResourceId: String(usage.balanceResourceId || ''),
                                        unit: usage.unit || '',
                                        minTransfer: usage.minTransfer || 0,
                                        productFamily: usage.productFamily || '',
                                        maxValue: usage.remain || 0,
                                      })
                                    }
                                  >
                                    转移
                                  </button>
                                ) : null}
                              </div>
                            </div>
                            <div className="usage-track">
                              <div className={barClass} style={{ width: `${percent}%` }}></div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  ) : null}
                  <div className="detail-desc">{offer.desc ? stripHtml(offer.desc) : ''}</div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
      <div
        id="activeEmptyState"
        className="empty-state"
        style={{ display: activeOffers.length === 0 ? 'block' : 'none' }}
      >
        当前没有已订购的生效套餐
      </div>
    </div>
  )
}

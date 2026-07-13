import type { Plan } from '@/types'
import { stripHtml } from '@/utils/mainPage'
import { UiIcon } from './UiIcon'

type PlanListProps = {
  readonly filteredPlans: Plan[]
  readonly noNumberMode: boolean
  readonly onAddToCart: (event: React.MouseEvent, plan: Plan) => void
  readonly onSelectPlan: (planId: string | null) => void
  readonly plansLoading: boolean
  readonly selectedPlanId: string | null
  readonly showFreePlans: boolean
  readonly visible: boolean
}

export function PlanList({
  filteredPlans,
  noNumberMode,
  onAddToCart,
  onSelectPlan,
  plansLoading,
  selectedPlanId,
  showFreePlans,
  visible,
}: PlanListProps): JSX.Element {
  return (
    <div id="planListContainer" style={{ display: visible ? undefined : 'none' }}>
      <div id="planList" className="plan-list">
        {plansLoading ? (
          <div className="loader">正在加载套餐…</div>
        ) : (
          filteredPlans.map((plan) => {
            const isOpen = selectedPlanId === plan.offerId
            return (
              <div key={plan.offerId} className={`plan-card ${isOpen ? 'open' : ''}`}>
                {plan.isVoWifi ? <div className="tag-vowifi">VoWiFi</div> : null}
                <button
                  type="button"
                  className="plan-card-disclosure"
                  aria-expanded={isOpen}
                  aria-controls={`plan-details-${plan.offerId}`}
                  onClick={() => onSelectPlan(isOpen ? null : plan.offerId)}
                >
                  <div className="card-header">
                    <div className="plan-name">{plan.name}</div>
                    <div className="plan-price">${plan.price}</div>
                  </div>
                  <div className="card-meta">
                    <span className="validity-badge">
                      <UiIcon className="validity-icon" name="calendar" size={16} /> {plan.validity}
                    </span>
                    <UiIcon className={`arrow ${isOpen ? 'open' : ''}`} name="chevron-down" />
                  </div>
                </button>
                <div
                  id={`plan-details-${plan.offerId}`}
                  className={`card-details ${isOpen ? 'open' : ''}`}
                  aria-hidden={!isOpen}
                  inert={isOpen ? undefined : ''}
                >
                  <div className="card-details-inner">
                    <div className="detail-desc">{stripHtml(plan.desc)}</div>
                    <button
                      className="buy-btn"
                      type="button"
                      style={{ display: noNumberMode && !showFreePlans ? 'none' : undefined }}
                      onClick={(event) => onAddToCart(event, plan)}
                    >
                      加入购物车
                    </button>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
      <div
        id="emptyState"
        className="empty-state"
        style={{ display: !plansLoading && filteredPlans.length === 0 ? 'block' : 'none' }}
      >
        无匹配结果
      </div>
    </div>
  )
}

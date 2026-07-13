import type { CmnAutoRefreshState } from '@/hooks/useCmn'
import type { CmnCheckResponse, Plan, Subscription, TransferDraft } from '@/types'
import type { CmnPattern } from '@/utils/cmnPattern'
import { ActiveOffersSection } from './ActiveOffersSection'
import { CmnSection } from './CmnSection'
import { MainFooter } from './MainFooter'
import { PlanList } from './PlanList'

type PlansContent = {
  readonly filteredPlans: Plan[]
  readonly noNumberMode: boolean
  readonly onAddToCart: (event: React.MouseEvent, plan: Plan) => void
  readonly onSelectPlan: (planId: string | null) => void
  readonly plansLoading: boolean
  readonly selectedPlanId: string | null
  readonly showFreePlans: boolean
  readonly visible: boolean
}

type OffersContent = {
  readonly currentSub: Subscription | null
  readonly onOpenTransfer: (event: React.MouseEvent, draft: TransferDraft) => void
  readonly onRefresh: () => void
  readonly onSelectOffer: (planId: string | null) => void
  readonly refreshingUsage: boolean
  readonly selectedPlanId: string | null
  readonly visible: boolean
}

type CmnContent = {
  readonly autoRefresh: CmnAutoRefreshState
  readonly canRefresh: boolean
  readonly cooldown: number
  readonly data: CmnCheckResponse['data'] | null
  readonly error: string
  readonly loading: boolean
  readonly numbers: string[]
  readonly numbersLoading: boolean
  readonly onAutoRefreshCancel: () => void
  readonly onAutoRefreshStart: () => void
  readonly onPatternChange: (pattern: string) => void
  readonly onRefresh: () => void
  readonly onSelectNumber: (number: string) => void
  readonly onSubmit: () => void
  readonly parsedPattern: CmnPattern
  readonly pattern: string
  readonly selectedNumber: string | null
  readonly visible: boolean
}

type MainPageContentProps = {
  readonly cmn: CmnContent
  readonly footerVisible: boolean
  readonly offers: OffersContent
  readonly plans: PlansContent
}

export function MainPageContent({ cmn, footerVisible, offers, plans }: MainPageContentProps): JSX.Element {
  return (
    <div className="content-wrapper">
      <PlanList {...plans} />

      <ActiveOffersSection {...offers} />
      <CmnSection {...cmn} />
      <MainFooter visible={footerVisible} />
    </div>
  )
}

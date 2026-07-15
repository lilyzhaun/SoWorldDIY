import { MainHeader } from '@/components/MainHeader'
import { MainPageContent } from '@/components/MainPageContent'
import { MainPageDialogs } from '@/components/MainPageDialogs'
import type { usePresenceValue } from '@/hooks/usePresenceValue'
import { isRootOpacityTransition } from '@/hooks/usePresenceValue'
import type { AvailableAccount, Category, Subscription } from '@/types'
import { SVG_SPRITE } from '@/assets/svgSprite'

type Presence = ReturnType<typeof usePresenceValue>

type MainPageViewProps = {
  readonly accountId: string
  readonly loaderPresence: Presence
  readonly header: {
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
  readonly content: {
    readonly plans: Parameters<typeof MainPageContent>[0]['plans']
    readonly offers: Parameters<typeof MainPageContent>[0]['offers']
    readonly cmn: Parameters<typeof MainPageContent>[0]['cmn']
    readonly footerVisible: boolean
  }
  readonly dialogs: Parameters<typeof MainPageDialogs>[0]
}

export function MainPageView({ accountId, loaderPresence, header, content, dialogs }: MainPageViewProps): JSX.Element {
  return (
    <>
      <div style={{ display: 'none' }} dangerouslySetInnerHTML={{ __html: SVG_SPRITE }} />
      <input type="hidden" id="current-account-id-ref" defaultValue={accountId} />
      {loaderPresence.value !== null ? (
        <div
          id="global-loader"
          className={`global-loader ${loaderPresence.phase}`}
          onTransitionEnd={(event) => {
            if (isRootOpacityTransition(event)) loaderPresence.completeExit()
          }}
        >
          <div className="loader-content">
            <div className="spinner"></div>
            <div className="loader-text">正在同步账户信息…</div>
          </div>
        </div>
      ) : null}

      <MainHeader
        availableAccounts={header.availableAccounts}
        balance={header.balance}
        category={header.category}
        currentSub={header.currentSub}
        noNumberMode={header.noNumberMode}
        onLogout={header.onLogout}
        onOpenHistory={header.onOpenHistory}
        onOpenInbox={header.onOpenInbox}
        onOpenSwitch={header.onOpenSwitch}
        onSearchChange={header.onSearchChange}
        onShowAlert={header.onShowAlert}
        onSwitchCategory={header.onSwitchCategory}
        search={header.search}
      />

      <MainPageContent
        plans={content.plans}
        offers={content.offers}
        cmn={content.cmn}
        footerVisible={content.footerVisible}
      />

      <MainPageDialogs {...dialogs} />
    </>
  )
}

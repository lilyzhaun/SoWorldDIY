import { createRoot } from 'react-dom/client'
import { flushSync } from 'react-dom'

import { WaitingState } from '@/components/WaitingState'
import { CmnRefreshButton } from '@/components/CmnRefreshButton'
import { ActiveOffersSection } from '@/components/ActiveOffersSection'
import { PlanList } from '@/components/PlanList'
import type { Plan, Subscription } from '@/types'
import '@/styles/main.css'

type AnimationFinishSample = {
  readonly animationCount: number
  readonly currentTime: number | null
  readonly finalTransform: string
  readonly initialTransform: string
  readonly playState: AnimationPlayState | ''
}

function isCssAnimation(animation: Animation): animation is CSSAnimation {
  return animation instanceof CSSAnimation
}

function getCssAnimations(element: Element): CSSAnimation[] {
  return element.getAnimations().filter(isCssAnimation)
}

function findWaitingAnimation(element: Element): CSSAnimation | null {
  const animations = getCssAnimations(element)
  if (animations.length === 0) return null
  const [animation] = animations
  const effect = animation?.effect
  if (
    animations.length !== 1 ||
    !animation ||
    animation.animationName !== 'waiting-state-spin' ||
    !(effect instanceof KeyframeEffect) ||
    effect.target !== element
  ) {
    throw new Error('Expected one waiting-state-spin CSSAnimation targeting the icon')
  }
  return animation
}

async function sampleNaturalFinish(element: Element): Promise<AnimationFinishSample> {
  const animation = findWaitingAnimation(element)
  const initialTransform = getComputedStyle(element).getPropertyValue('transform')
  if (animation) await animation.finished
  const currentTime = animation?.currentTime
  return {
    animationCount: getCssAnimations(element).length,
    currentTime: typeof currentTime === 'number' ? currentTime : null,
    finalTransform: getComputedStyle(element).getPropertyValue('transform'),
    initialTransform,
    playState: animation?.playState ?? '',
  }
}

const plans: Plan[] = []

const subscription: Subscription = {
  subscriptionId: 'sub-1',
  activeOffers: [],
}

function getElement<T extends Element>(selector: string, expected: { new (...args: never[]): T }): T {
  const element = document.querySelector(selector)
  if (!(element instanceof expected)) {
    throw new Error(`Missing expected element: ${selector}`)
  }
  return element
}

function getCssValue(selector: string, property: string): string {
  const element = document.querySelector(selector)
  return element ? getComputedStyle(element).getPropertyValue(property) : ''
}

function isVisible(element: Element): boolean {
  const style = getComputedStyle(element)
  const bounds = element.getBoundingClientRect()
  return (
    style.display !== 'none' &&
    style.visibility === 'visible' &&
    Number(style.opacity) > 0 &&
    bounds.width > 0 &&
    bounds.height > 0
  )
}

async function run(): Promise<void> {
  const root = document.getElementById('root')
  if (!(root instanceof HTMLDivElement)) {
    throw new Error('Expected #root element')
  }

  flushSync(() =>
    createRoot(root).render(
      <main id="waiting-state-harness" style={{ display: 'grid', gap: 12, padding: 16 }}>
        <section id="waiting-state-primitives">
          <WaitingState phase="requesting" iconClassName="waiting-btn-icon">
            正在请求
          </WaitingState>
          <WaitingState phase="cooldown" iconClassName="waiting-cooldown-icon">
            冷却中
          </WaitingState>
        </section>
        <section id="cmn-refresh-primitives">
          <CmnRefreshButton
            autoRefresh={{ kind: 'idle', message: '' }}
            canRefresh
            cooldown={0}
            mode="initial"
            numbersLoading
            onAutoRefreshCancel={() => undefined}
            onAutoRefreshStart={() => undefined}
            onRefresh={() => undefined}
            pattern=""
            validPattern={false}
            visible
          />
          <CmnRefreshButton
            autoRefresh={{ kind: 'idle', message: '' }}
            canRefresh={false}
            cooldown={4}
            mode="subsequent"
            numbersLoading={false}
            onAutoRefreshCancel={() => undefined}
            onAutoRefreshStart={() => undefined}
            onRefresh={() => undefined}
            pattern="666"
            validPattern
            visible
          />
        </section>
        <section id="plan-list-surface">
          <PlanList
            filteredPlans={plans}
            noNumberMode={false}
            onAddToCart={() => undefined}
            onSelectPlan={() => undefined}
            plansLoading
            selectedPlanId={null}
            showFreePlans
            visible
          />
        </section>
        <section id="active-offers-surface">
          <ActiveOffersSection
            currentSub={subscription}
            onOpenTransfer={() => undefined}
            onRefresh={() => undefined}
            onSelectOffer={() => undefined}
            refreshingUsage
            selectedPlanId="sub-offer-1"
            visible
          />
        </section>
      </main>,
    ),
  )

  const harness = document.getElementById('waiting-state-harness')
  if (!(harness instanceof HTMLElement)) {
    throw new Error('Missing #waiting-state-harness root after render')
  }

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const requestingIcon = getElement<SVGSVGElement>('#waiting-state-primitives .waiting-btn-icon', SVGSVGElement)
  const cooldownIcon = getElement<SVGSVGElement>('#waiting-state-primitives .waiting-cooldown-icon', SVGSVGElement)
  const requestingMarker = getElement<HTMLElement>(
    '#waiting-state-primitives .waiting-btn-icon + .waiting-state-marker',
    HTMLElement,
  )
  const cooldownMarker = getElement<HTMLElement>(
    '#waiting-state-primitives .waiting-cooldown-icon + .waiting-state-marker',
    HTMLElement,
  )

  const requestAnimationName = getCssValue('#waiting-state-primitives .waiting-btn-icon', 'animation-name')
  const cooldownAnimationName = getCssValue('#waiting-state-primitives .waiting-cooldown-icon', 'animation-name')
  const requestDuration = getCssValue('#waiting-state-primitives .waiting-btn-icon', 'animation-duration')
  const cooldownDuration = getCssValue('#waiting-state-primitives .waiting-cooldown-icon', 'animation-duration')
  const requestingCopy =
    document.querySelector('span.waiting-state[data-waiting-phase="requesting"]')?.textContent?.trim() ?? ''
  const [requestAnimation, cooldownAnimation] = await Promise.all([
    sampleNaturalFinish(requestingIcon),
    sampleNaturalFinish(cooldownIcon),
  ])

  const planListLoader = getElement<HTMLElement>('#plan-list-surface .loader', HTMLDivElement)
  const planListBusy = planListLoader.getAttribute('aria-busy')
  const planListLive = planListLoader.getAttribute('aria-live')
  const planListRole = planListLoader.getAttribute('role')
  const activeRefresh = getElement<HTMLButtonElement>('#active-offers-surface #refreshUsageBtn', HTMLButtonElement)
  const cmnInitialButton = getElement<HTMLElement>('#cmn-refresh-primitives #initLoadBtn', HTMLButtonElement)
  const cmnCooldownButton = getElement<HTMLElement>('#cmn-refresh-primitives #refreshNumBtn', HTMLButtonElement)

  const cmnRequestingState = cmnInitialButton.querySelector('.waiting-state')?.getAttribute('data-waiting-phase') ?? ''
  const cmnCooldownState = cmnCooldownButton.querySelector('.waiting-state')?.getAttribute('data-waiting-phase') ?? ''
  const cmnRequestingIcon = getElement<SVGSVGElement>(
    '#cmn-refresh-primitives #initLoadBtn .refresh-btn-icon',
    SVGSVGElement,
  )
  const cmnCooldownIcon = getElement<SVGSVGElement>(
    '#cmn-refresh-primitives #refreshNumBtn .refresh-btn-icon',
    SVGSVGElement,
  )
  const cmnRequestingStyle = getComputedStyle(cmnRequestingIcon)
  const cmnCooldownStyle = getComputedStyle(cmnCooldownIcon)

  harness.setAttribute('data-requesting-phase', 'requesting')
  harness.setAttribute('data-cooldown-phase', 'cooldown')
  harness.setAttribute('data-requesting-animation-name', requestAnimationName)
  harness.setAttribute('data-cooldown-animation-name', cooldownAnimationName)
  harness.setAttribute('data-requesting-duration', requestDuration)
  harness.setAttribute('data-cooldown-duration', cooldownDuration)
  harness.setAttribute('data-requesting-initial-transform', requestAnimation.initialTransform)
  harness.setAttribute('data-requesting-final-transform', requestAnimation.finalTransform)
  harness.setAttribute('data-requesting-final-current-time', String(requestAnimation.currentTime))
  harness.setAttribute('data-requesting-final-play-state', requestAnimation.playState)
  harness.setAttribute('data-requesting-animation-count', String(requestAnimation.animationCount))
  harness.setAttribute('data-cooldown-initial-transform', cooldownAnimation.initialTransform)
  harness.setAttribute('data-cooldown-final-transform', cooldownAnimation.finalTransform)
  harness.setAttribute('data-cooldown-final-current-time', String(cooldownAnimation.currentTime))
  harness.setAttribute('data-cooldown-final-play-state', cooldownAnimation.playState)
  harness.setAttribute('data-cooldown-animation-count', String(cooldownAnimation.animationCount))
  harness.setAttribute('data-requesting-visible', String(requestingCopy.length > 0))
  harness.setAttribute('data-requesting-icon-visible', String(isVisible(requestingIcon)))
  harness.setAttribute('data-cooldown-icon-visible', String(isVisible(cooldownIcon)))
  harness.setAttribute('data-requesting-marker-visible', String(isVisible(requestingMarker)))
  harness.setAttribute('data-cooldown-marker-visible', String(isVisible(cooldownMarker)))
  harness.setAttribute(
    'data-requesting-marker',
    String(requestingMarker.getAttribute('data-waiting-marker') === 'true'),
  )
  harness.setAttribute('data-cooldown-marker', String(cooldownMarker.getAttribute('data-waiting-marker') === 'true'))
  const requestingMarkerStyle = getComputedStyle(requestingMarker)
  const cooldownMarkerStyle = getComputedStyle(cooldownMarker)
  harness.setAttribute('data-requesting-marker-background', requestingMarkerStyle.backgroundColor)
  harness.setAttribute('data-requesting-marker-box-shadow', requestingMarkerStyle.boxShadow)
  harness.setAttribute('data-cooldown-marker-background', cooldownMarkerStyle.backgroundColor)
  harness.setAttribute('data-cooldown-marker-box-shadow', cooldownMarkerStyle.boxShadow)
  harness.setAttribute('data-planlist-aria-busy', String(planListBusy))
  harness.setAttribute('data-planlist-live', String(planListLive))
  harness.setAttribute('data-planlist-role', String(planListRole))
  harness.setAttribute('data-active-refresh-aria-busy', String(activeRefresh.getAttribute('aria-busy') === 'true'))
  harness.setAttribute('data-cmn-requesting-phase', cmnRequestingState)
  harness.setAttribute('data-cmn-cooldown-phase', cmnCooldownState)
  harness.setAttribute('data-cmn-requesting-animation-name', cmnRequestingStyle.animationName)
  harness.setAttribute('data-cmn-cooldown-animation-name', cmnCooldownStyle.animationName)
  harness.setAttribute('data-cmn-requesting-duration', cmnRequestingStyle.animationDuration)
  harness.setAttribute('data-cmn-cooldown-duration', cmnCooldownStyle.animationDuration)
  harness.setAttribute('data-cmn-requesting-iteration-count', cmnRequestingStyle.animationIterationCount)
  harness.setAttribute('data-cmn-cooldown-iteration-count', cmnCooldownStyle.animationIterationCount)
  harness.setAttribute('data-cmn-requesting-animation-count', String(getCssAnimations(cmnRequestingIcon).length))
  harness.setAttribute('data-cmn-cooldown-animation-count', String(getCssAnimations(cmnCooldownIcon).length))
  harness.setAttribute('data-reduced-motion', String(reduced))
  harness.setAttribute('data-complete', 'true')
}

void run()

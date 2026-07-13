import type { Plan, Subscription } from '@/types'

export type ProfileSubscriptionSelection = {
  readonly currentSubId: string
  readonly noNumberMode: boolean
}

export function selectProfileSubscription(
  subscriptions: readonly Subscription[],
  backendCurrent: Subscription | undefined,
  currentSubId: string,
): ProfileSubscriptionSelection {
  const selected = currentSubId
    ? subscriptions.find((subscription) => subscription.subscriptionId === currentSubId)
    : undefined
  const target = selected ?? backendCurrent ?? subscriptions[0]

  return target?.subscriptionId
    ? { currentSubId: target.subscriptionId, noNumberMode: false }
    : { currentSubId: '', noNumberMode: true }
}

export function sortPlansByPrice(plans: readonly Plan[]): Plan[] {
  return [...plans].sort((left, right) => left.price - right.price)
}

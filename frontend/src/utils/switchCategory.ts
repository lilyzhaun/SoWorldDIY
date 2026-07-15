type SwitchCategoryState = {
  readonly allTabClickCount: number
  readonly showFreePlans: boolean
}

type SwitchCategoryResult = {
  readonly allTabClickCount: number
  readonly showFreePlans: boolean
  readonly revealFreePlans: boolean
}

export function nextAllTabState(state: SwitchCategoryState): SwitchCategoryResult {
  const nextCount = state.allTabClickCount + 1
  if (nextCount >= 5 && !state.showFreePlans) {
    return { allTabClickCount: 0, showFreePlans: true, revealFreePlans: true }
  }
  return { allTabClickCount: nextCount, showFreePlans: state.showFreePlans, revealFreePlans: false }
}

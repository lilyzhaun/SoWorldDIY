import { useCallback, useState } from 'react'
import { createRoot } from 'react-dom/client'

import { CmnSection } from '@/components/CmnSection'
import type { CmnAutoRefreshState, CmnNumbersMode } from '@/hooks/useCmn'
import '@/styles/main.css'
import { parseCmnPattern } from '@/utils/cmnPattern'

const wait = (milliseconds: number): Promise<void> => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

export function Harness(): JSX.Element {
  const [pattern, setPattern] = useState('')
  const [autoRefresh, setAutoRefresh] = useState<CmnAutoRefreshState>({ kind: 'idle', message: '' })
  const [numbers, setNumbers] = useState(['12345678'])
  const [refreshes, setRefreshes] = useState(0)
  const [starts, setStarts] = useState(0)
  const [cancels, setCancels] = useState(0)
  const [canRefresh, setCanRefresh] = useState(true)
  const [visible, setVisible] = useState(true)
  const [numbersLoading, setNumbersLoading] = useState(false)
  const [numbersMode, setNumbersMode] = useState<CmnNumbersMode>('subsequent')
  const [cooldown, setCooldown] = useState(0)
  const [callbackVersion, setCallbackVersion] = useState(0)

  const handleAutoRefreshStart = useCallback((): void => {
    setStarts((value) => value + 1)
    setNumbers(['66612345'])
    setNumbersLoading(true)
    setAutoRefresh({
      kind: 'running',
      attempt: 1,
      phase: 'requesting',
      message: `正在自动查找第 1 批号码（${callbackVersion}）`,
    })
  }, [callbackVersion])

  return (
    <main id="harness" data-refreshes={refreshes} data-starts={starts} data-cancels={cancels}>
      <button id="set-empty" type="button" onClick={() => setPattern('')}>
        empty
      </button>
      <button id="set-invalid" type="button" onClick={() => setPattern('[')}>
        invalid
      </button>
      <button id="set-valid" type="button" onClick={() => setPattern('666')}>
        valid
      </button>
      <button id="set-hidden" type="button" onClick={() => setVisible(false)}>
        hidden
      </button>
      <button id="set-visible" type="button" onClick={() => setVisible(true)}>
        visible
      </button>
      <button id="set-cannot-refresh" type="button" onClick={() => setCanRefresh(false)}>
        cannot refresh
      </button>
      <button id="set-can-refresh" type="button" onClick={() => setCanRefresh(true)}>
        can refresh
      </button>
      <button id="set-loaded" type="button" onClick={() => setNumbersLoading(false)}>
        loaded
      </button>
      <button id="set-loading" type="button" onClick={() => setNumbersLoading(true)}>
        loading
      </button>
      <button id="set-initial" type="button" onClick={() => setNumbersMode('initial')}>
        initial
      </button>
      <button id="set-subsequent" type="button" onClick={() => setNumbersMode('subsequent')}>
        subsequent
      </button>
      <button id="set-cooldown" type="button" onClick={() => setCooldown(3)}>
        cooldown
      </button>
      <button id="clear-cooldown" type="button" onClick={() => setCooldown(0)}>
        clear cooldown
      </button>
      <button
        id="set-running"
        type="button"
        onClick={() =>
          setAutoRefresh({ kind: 'running', attempt: 1, phase: 'requesting', message: '正在自动查找第 1 批号码' })
        }
      >
        running
      </button>
      <button id="set-idle" type="button" onClick={() => setAutoRefresh({ kind: 'idle', message: '' })}>
        idle
      </button>
      <button id="change-callback" type="button" onClick={() => setCallbackVersion((value) => value + 1)}>
        callback
      </button>
      <div className="content-wrapper">
        <CmnSection
          autoRefresh={autoRefresh}
          canRefresh={canRefresh}
          cooldown={cooldown}
          data={{ offerId: 'offer-1', offerSubType: 'CMN', price: 28 }}
          error=""
          loading={false}
          numbers={numbers}
          numbersLoading={numbersLoading}
          numbersMode={numbersMode}
          onAutoRefreshCancel={() => {
            setCancels((value) => value + 1)
            setNumbersLoading(false)
            setAutoRefresh({ kind: 'idle', message: '已取消自动查找' })
          }}
          onAutoRefreshStart={handleAutoRefreshStart}
          onPatternChange={setPattern}
          onRefresh={() => setRefreshes((value) => value + 1)}
          onSelectNumber={() => undefined}
          onSubmit={() => undefined}
          parsedPattern={parseCmnPattern(pattern)}
          pattern={pattern}
          selectedNumber={null}
          visible={visible}
        />
      </div>
    </main>
  )
}

function pointer(type: string, button = 0): PointerEvent {
  return new PointerEvent(type, { bubbles: true, button, isPrimary: true, pointerId: 1, pointerType: 'touch' })
}

function dispatchContextMenu(button: HTMLButtonElement): boolean {
  const event = new MouseEvent('contextmenu', { bubbles: true, cancelable: true })
  button.dispatchEvent(event)
  return event.defaultPrevented
}

async function run(): Promise<void> {
  createRoot(document.getElementById('root') as HTMLElement).render(<Harness />)
  await wait(0)
  const refreshButton = document.getElementById('refreshNumBtn') as HTMLButtonElement
  Object.defineProperties(refreshButton, {
    setPointerCapture: { value: () => undefined },
    hasPointerCapture: { value: () => false },
    releasePointerCapture: { value: () => undefined },
  })

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.getElementById('set-loading')?.click()
    document.getElementById('set-cannot-refresh')?.click()
    await wait(0)
    const harness = document.getElementById('harness')
    const icon = document.querySelector('#refreshNumBtn .refresh-btn-icon')
    harness?.setAttribute('data-loading-animation-name', icon ? getComputedStyle(icon).animationName : '')
    harness?.setAttribute('data-reduced-motion', 'true')
    harness?.setAttribute('data-complete', 'true')
    return
  }

  refreshButton.click()
  document.getElementById('set-empty')?.click()
  refreshButton.dispatchEvent(pointer('pointerdown'))
  const emptyContextMenuPrevented = dispatchContextMenu(refreshButton)
  await wait(600)
  refreshButton.dispatchEvent(pointer('pointerup'))
  refreshButton.click()

  document.getElementById('set-invalid')?.click()
  await wait(0)
  const pointerFocusSentinel = document.getElementById('set-valid') as HTMLButtonElement
  pointerFocusSentinel.focus()
  refreshButton.dispatchEvent(pointer('pointerdown'))
  const invalidContextMenuPrevented = dispatchContextMenu(refreshButton)
  await wait(600)
  refreshButton.dispatchEvent(pointer('pointerup'))
  refreshButton.click()

  document.getElementById('set-valid')?.click()
  await wait(0)
  const startsBeforeStaleArms = document.getElementById('harness')?.dataset.starts ?? ''
  const cancelArmWith = async (controlId: string): Promise<void> => {
    refreshButton.dispatchEvent(pointer('pointerdown'))
    document.getElementById(controlId)?.click()
    await wait(600)
    refreshButton.dispatchEvent(pointer('pointercancel'))
  }
  await cancelArmWith('set-invalid')
  document.getElementById('set-valid')?.click()
  await wait(0)
  await cancelArmWith('set-hidden')
  document.getElementById('set-visible')?.click()
  await wait(0)
  await cancelArmWith('set-cannot-refresh')
  document.getElementById('set-can-refresh')?.click()
  await wait(0)
  await cancelArmWith('set-running')
  document.getElementById('set-idle')?.click()
  await wait(0)
  await cancelArmWith('change-callback')
  const startsAfterStaleArms = document.getElementById('harness')?.dataset.starts ?? ''

  refreshButton.dispatchEvent(pointer('pointerdown', 2))
  const rightClickContextMenuPrevented = dispatchContextMenu(refreshButton)
  refreshButton.dispatchEvent(pointer('pointerup', 2))

  refreshButton.dispatchEvent(pointer('pointerdown'))
  const armedContextMenuPrevented = dispatchContextMenu(refreshButton)
  refreshButton.dispatchEvent(pointer('pointerup'))

  refreshButton.dispatchEvent(pointer('pointerdown'))
  const idleGridTop = document.getElementById('numGrid')?.getBoundingClientRect().top ?? 0
  const idleActionsTop = document.querySelector('.cmn-actions')?.getBoundingClientRect().top ?? 0
  const idleButtonHeight = refreshButton.getBoundingClientRect().height
  await wait(600)
  refreshButton.dispatchEvent(pointer('pointerup'))
  refreshButton.click()
  await wait(0)
  const pointerFocusPreserved = document.activeElement === pointerFocusSentinel

  const runningGridTop = document.getElementById('numGrid')?.getBoundingClientRect().top ?? 0
  const runningActionsTop = document.querySelector('.cmn-actions')?.getBoundingClientRect().top ?? 0
  const runningButtonHeight = refreshButton.getBoundingClientRect().height
  document.getElementById('set-loaded')?.click()
  await wait(0)
  const cancelsBeforeExplicitClick = document.getElementById('harness')?.dataset.cancels ?? ''
  refreshButton.click()
  await wait(0)

  refreshButton.dispatchEvent(pointer('pointerdown'))
  await wait(600)
  refreshButton.dispatchEvent(pointer('pointercancel'))
  await wait(10)
  refreshButton.click()
  await wait(0)

  const keyboardButton = document.getElementById('cmn-auto-refresh-start') as HTMLButtonElement
  keyboardButton.focus()
  const keyboardFocused = document.activeElement === keyboardButton
  const startsBeforeKeyboard = document.getElementById('harness')?.dataset.starts ?? ''
  keyboardButton.click()
  await wait(20)
  const startsAfterKeyboard = document.getElementById('harness')?.dataset.starts ?? ''
  const keyboardFocusTransferred = document.activeElement === refreshButton
  refreshButton.click()
  await wait(0)

  document.getElementById('set-idle')?.click()
  document.getElementById('set-loaded')?.click()
  document.getElementById('set-can-refresh')?.click()
  document.getElementById('set-initial')?.click()
  await wait(0)
  const initialButton = document.getElementById('initLoadBtn') as HTMLButtonElement
  const initialIdleHeight = initialButton.getBoundingClientRect().height
  const initialIdleCorrect = initialButton.textContent?.trim() === '获取一组新号码'

  document.getElementById('set-loading')?.click()
  document.getElementById('set-cannot-refresh')?.click()
  await wait(0)
  const initialLoadingHeight = initialButton.getBoundingClientRect().height
  const initialLoadingCorrect = initialButton.textContent?.trim() === '正在获取号码…'
  const initialRefreshIcon = initialButton.querySelector('.refresh-btn-icon')
  const loadingAnimationName = initialRefreshIcon
    ? getComputedStyle(initialRefreshIcon as SVGElement).animationName
    : 'none'

  document.getElementById('set-subsequent')?.click()
  await wait(0)
  const subsequentButton = document.getElementById('refreshNumBtn') as HTMLButtonElement
  const subsequentLoadingCorrect = subsequentButton.textContent?.trim() === '正在换一批…'
  document.getElementById('set-loaded')?.click()
  document.getElementById('set-cooldown')?.click()
  await wait(0)
  const cooldownCorrect = subsequentButton.textContent?.trim() === '换一批（3s）'
  const countdown = document.getElementById('refresh-timer')
  const countdownTabular = countdown ? getComputedStyle(countdown).fontVariantNumeric.includes('tabular-nums') : false
  document.getElementById('clear-cooldown')?.click()
  await wait(0)
  const zeroSecondsHidden = !subsequentButton.textContent?.includes('0s')

  const harness = document.getElementById('harness')
  harness?.setAttribute('data-cancels-before-explicit-click', cancelsBeforeExplicitClick)
  harness?.setAttribute('data-highlighted', String(document.querySelector('.cmn-match')?.textContent === '666'))
  harness?.setAttribute('data-empty-contextmenu-prevented', String(emptyContextMenuPrevented))
  harness?.setAttribute('data-invalid-contextmenu-prevented', String(invalidContextMenuPrevented))
  harness?.setAttribute('data-right-contextmenu-prevented', String(rightClickContextMenuPrevented))
  harness?.setAttribute('data-armed-contextmenu-prevented', String(armedContextMenuPrevented))
  harness?.setAttribute('data-stale-arms-started', String(Number(startsAfterStaleArms) - Number(startsBeforeStaleArms)))
  harness?.setAttribute('data-keyboard-focused', String(keyboardFocused))
  harness?.setAttribute('data-keyboard-focus-transferred', String(keyboardFocusTransferred))
  harness?.setAttribute(
    'data-keyboard-started',
    String(Number(startsAfterKeyboard) === Number(startsBeforeKeyboard) + 1),
  )
  harness?.setAttribute('data-pointer-focus-preserved', String(pointerFocusPreserved))
  harness?.setAttribute('data-grid-shift-ok', String(Math.abs(runningGridTop - idleGridTop) <= 2))
  harness?.setAttribute('data-actions-shift-ok', String(Math.abs(runningActionsTop - idleActionsTop) <= 2))
  harness?.setAttribute('data-button-height-shift-ok', String(Math.abs(runningButtonHeight - idleButtonHeight) <= 2))
  harness?.setAttribute('data-initial-idle-correct', String(initialIdleCorrect))
  harness?.setAttribute('data-initial-loading-correct', String(initialLoadingCorrect))
  harness?.setAttribute('data-initial-height-stable', String(Math.abs(initialLoadingHeight - initialIdleHeight) <= 2))
  harness?.setAttribute('data-subsequent-loading-correct', String(subsequentLoadingCorrect))
  harness?.setAttribute('data-cooldown-correct', String(cooldownCorrect))
  harness?.setAttribute('data-countdown-tabular', String(countdownTabular))
  harness?.setAttribute('data-zero-seconds-hidden', String(zeroSecondsHidden))
  harness?.setAttribute('data-loading-animation-name', loadingAnimationName)
  harness?.setAttribute('data-reduced-motion', String(window.matchMedia('(prefers-reduced-motion: reduce)').matches))
  const rootWidth = document.getElementById('root')?.getBoundingClientRect().width ?? 0
  harness?.setAttribute('data-viewport-width', String(window.innerWidth))
  harness?.setAttribute(
    'data-root-fills-viewport',
    String(Math.abs(rootWidth - document.documentElement.clientWidth) <= 1),
  )
  harness?.setAttribute('data-complete', 'true')
}

void run()

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { CmnRefreshButton, resolveCmnRefreshButtonState } from './CmnRefreshButton'

function renderButton(overrides: Partial<Parameters<typeof CmnRefreshButton>[0]> = {}): string {
  return renderToStaticMarkup(
    <CmnRefreshButton
      autoRefresh={{ kind: 'idle', message: '' }}
      canRefresh
      cooldown={0}
      mode="subsequent"
      numbersLoading={false}
      onAutoRefreshCancel={vi.fn()}
      onAutoRefreshStart={vi.fn()}
      onRefresh={vi.fn()}
      pattern="666"
      validPattern
      visible
      {...overrides}
    />,
  )
}

describe('resolveCmnRefreshButtonState', () => {
  it('lets auto-refresh running take precedence over loading and cooldown', () => {
    expect(
      resolveCmnRefreshButtonState({
        autoRefresh: { kind: 'running', attempt: 2, phase: 'requesting', message: '正在自动查找第 2 批号码' },
        canRefresh: false,
        cooldown: 3,
        numbersLoading: true,
      }),
    ).toEqual({ kind: 'running', attempt: 2, phase: 'requesting' })
  })

  it('carries the auto-refresh cooldown phase into the running state', () => {
    expect(
      resolveCmnRefreshButtonState({
        autoRefresh: { kind: 'running', attempt: 2, phase: 'cooldown', message: '正在自动查找第 2 批号码' },
        canRefresh: false,
        cooldown: 0,
        numbersLoading: false,
      }),
    ).toEqual({ kind: 'running', attempt: 2, phase: 'cooldown' })
  })

  it('lets loading take precedence over an active cooldown', () => {
    expect(
      resolveCmnRefreshButtonState({
        autoRefresh: { kind: 'idle', message: '' },
        canRefresh: false,
        cooldown: 3,
        numbersLoading: true,
      }),
    ).toEqual({ kind: 'loading' })
  })

  it('keeps cooldown only while seconds stay positive', () => {
    expect(
      resolveCmnRefreshButtonState({
        autoRefresh: { kind: 'idle', message: '' },
        canRefresh: false,
        cooldown: 2,
        numbersLoading: false,
      }),
    ).toEqual({ kind: 'cooldown', seconds: 2 })
    expect(
      resolveCmnRefreshButtonState({
        autoRefresh: { kind: 'idle', message: '' },
        canRefresh: false,
        cooldown: 0,
        numbersLoading: false,
      }),
    ).toEqual({ kind: 'idle' })
  })

  it('falls back to idle when refresh is available', () => {
    expect(
      resolveCmnRefreshButtonState({
        autoRefresh: { kind: 'idle', message: '' },
        canRefresh: true,
        cooldown: 0,
        numbersLoading: false,
      }),
    ).toEqual({ kind: 'idle' })
  })
})

describe('CmnRefreshButton presentation', () => {
  it('renders the initial idle state with a search icon and load copy', () => {
    const html = renderButton({ mode: 'initial', pattern: '', validPattern: false })

    expect(html).toContain('id="initLoadBtn"')
    expect(html).toContain('data-ui-icon="search"')
    expect(html).toContain('获取一组新号码')
    expect(html).not.toContain('disabled=""')
    expect(html).not.toContain('aria-busy')
    expect(html).not.toContain('aria-describedby')
  })

  it('renders the initial loading state with a spinning refresh icon and no 0s', () => {
    const html = renderButton({
      mode: 'initial',
      pattern: '',
      validPattern: false,
      numbersLoading: true,
      canRefresh: false,
    })

    expect(html).toContain('正在获取号码…')
    expect(html).toContain('data-ui-icon="refresh"')
    expect(html).toContain('is-loading')
    expect(html).toContain('data-waiting-phase="requesting"')
    expect(html).toContain('waiting-state-marker')
    expect(html).toContain('disabled=""')
    expect(html).toContain('aria-busy="true"')
    expect(html).not.toContain('0s')
  })

  it('renders the subsequent idle state with refresh copy', () => {
    const html = renderButton()

    expect(html).toContain('id="refreshNumBtn"')
    expect(html).toContain('class="refresh-btn cmn-auto-refresh-button"')
    expect(html).toContain('换一批')
    expect(html).toContain('aria-describedby="cmn-auto-refresh-hint cmn-auto-refresh-status"')
    expect(html).not.toContain('disabled=""')
  })

  it('renders the subsequent loading state instead of a zero-second cooldown', () => {
    const html = renderButton({ canRefresh: false, cooldown: 0, numbersLoading: true })

    expect(html).toContain('正在换一批…')
    expect(html).toContain('is-loading')
    expect(html).toContain('data-waiting-phase="requesting"')
    expect(html).toContain('aria-busy="true"')
    expect(html).toContain('disabled=""')
    expect(html).not.toContain('0s')
  })

  it.each([3, 2, 1])('renders the positive %s-second tabular countdown while cooling down', (seconds) => {
    const html = renderButton({ canRefresh: false, cooldown: seconds })

    expect(html).toContain(`换一批（<span class="cmn-refresh-countdown" id="refresh-timer">${seconds}s</span>）`)
    expect(html).toContain('data-waiting-phase="cooldown"')
    expect(html).toContain('disabled=""')
    expect(html).not.toContain('aria-busy')
    expect(html).not.toContain('is-loading')
  })

  it('never renders a zero-second countdown when refresh is blocked without cooldown', () => {
    const html = renderButton({ canRefresh: false, cooldown: 0 })

    expect(html).toContain('换一批')
    expect(html).toContain('disabled=""')
    expect(html).not.toContain('（0s）')
    expect(html).not.toContain('refresh-timer')
  })

  it('keeps the idle state free of any waiting phase marker', () => {
    const html = renderButton()

    expect(html).not.toContain('data-waiting-phase')
    expect(html).not.toContain('waiting-state-marker')
  })

  it('keeps the running attempt and cancel copy with cancel semantics', () => {
    const html = renderButton({
      autoRefresh: { kind: 'running', attempt: 4, phase: 'requesting', message: '正在自动查找第 4 批号码' },
      canRefresh: false,
      cooldown: 2,
      numbersLoading: true,
    })

    expect(html).toContain('自动查找 4/20')
    expect(html).toContain('点击取消')
    expect(html).toContain('is-running')
    expect(html).toContain('data-waiting-phase="requesting"')
    expect(html).toContain('aria-busy="true"')
    expect(html).not.toContain('disabled=""')
    expect(html).not.toContain('正在换一批')
  })

  it('exposes the auto-refresh cooldown phase while waiting between attempts', () => {
    const html = renderButton({
      autoRefresh: { kind: 'running', attempt: 4, phase: 'cooldown', message: '正在自动查找第 4 批号码' },
    })

    expect(html).toContain('自动查找 4/20')
    expect(html).toContain('data-waiting-phase="cooldown"')
    expect(html).toContain('is-running')
    expect(html).not.toContain('disabled=""')
  })

  it('narrows aria-describedby to the status region when the pattern is invalid', () => {
    const html = renderButton({ validPattern: false })

    expect(html).toContain('aria-describedby="cmn-auto-refresh-status"')
    expect(html).not.toContain('cmn-auto-refresh-hint')
  })
})

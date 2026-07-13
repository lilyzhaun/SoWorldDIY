import { useEffect, useLayoutEffect, useRef } from 'react'

import type { CmnAutoRefreshState } from '@/hooks/useCmn'
import type { CmnCheckResponse } from '@/types'
import { findCmnPatternRanges, segmentCmnCandidate, type CmnPattern } from '@/utils/cmnPattern'
import { UiIcon } from './UiIcon'

const LONG_PRESS_MS = 550

type CmnSectionProps = {
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

export function CmnSection({ autoRefresh, canRefresh, cooldown, data, error, loading, numbers, numbersLoading, onAutoRefreshCancel, onAutoRefreshStart, onPatternChange, onRefresh, onSelectNumber, onSubmit, parsedPattern, pattern, selectedNumber, visible }: CmnSectionProps): JSX.Element {
  const longPressTimerRef = useRef<number | null>(null)
  const suppressClickFallbackRef = useRef<number | null>(null)
  const armedPointerRef = useRef<number | null>(null)
  const suppressClickRef = useRef(false)
  const visibleNumbers = numbers.slice(0, 9)
  const patternError = parsedPattern.kind === 'invalid' ? parsedPattern.message : ''
  const validPattern = parsedPattern.kind === 'literal' || parsedPattern.kind === 'regex'
  const running = autoRefresh.kind === 'running'
  const gestureEligibilityRef = useRef({ canRefresh, onAutoRefreshStart, pattern, running, validPattern, visible })

  const clearLongPress = (): void => {
    if (longPressTimerRef.current !== null) window.clearTimeout(longPressTimerRef.current)
    longPressTimerRef.current = null
    armedPointerRef.current = null
  }

  const cancelPendingLongPress = (): void => {
    if (longPressTimerRef.current === null) return
    window.clearTimeout(longPressTimerRef.current)
    longPressTimerRef.current = null
    armedPointerRef.current = null
  }

  const clearClickSuppression = (): void => {
    if (suppressClickFallbackRef.current !== null) window.clearTimeout(suppressClickFallbackRef.current)
    suppressClickFallbackRef.current = null
    suppressClickRef.current = false
  }

  useEffect(() => () => {
    clearLongPress()
    clearClickSuppression()
  }, [])

  useLayoutEffect(() => {
    gestureEligibilityRef.current = { canRefresh, onAutoRefreshStart, pattern, running, validPattern, visible }
    cancelPendingLongPress()
  }, [canRefresh, onAutoRefreshStart, pattern, running, validPattern, visible])

  const handlePointerDown = (event: React.PointerEvent<HTMLButtonElement>): void => {
    clearClickSuppression()
    if (event.button !== 0 || !event.isPrimary || running || !validPattern || !canRefresh) return
    armedPointerRef.current = event.pointerId
    const pointerId = event.pointerId
    const armedEligibility = gestureEligibilityRef.current
    event.currentTarget.setPointerCapture?.(event.pointerId)
    longPressTimerRef.current = window.setTimeout(() => {
      longPressTimerRef.current = null
      const current = gestureEligibilityRef.current
      if (armedPointerRef.current !== pointerId || !current.canRefresh || current.running || !current.validPattern || !current.visible || current.pattern !== armedEligibility.pattern || current.onAutoRefreshStart !== armedEligibility.onAutoRefreshStart) return
      suppressClickRef.current = true
      current.onAutoRefreshStart()
    }, LONG_PRESS_MS)
  }

  const handlePointerEnd = (event: React.PointerEvent<HTMLButtonElement>): void => {
    if (armedPointerRef.current !== event.pointerId) return
    clearLongPress()
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) event.currentTarget.releasePointerCapture?.(event.pointerId)
    if (suppressClickRef.current) {
      suppressClickFallbackRef.current = window.setTimeout(clearClickSuppression, 0)
    }
  }

  const handleRefreshClick = (): void => {
    if (suppressClickRef.current) {
      clearClickSuppression()
      return
    }
    if (running) {
      onAutoRefreshCancel()
      return
    }
    onRefresh()
  }

  const handleContextMenu = (event: React.MouseEvent<HTMLButtonElement>): void => {
    if (armedPointerRef.current !== null) event.preventDefault()
  }

  const describedBy = [
    'cmn-pattern-description',
    patternError ? 'cmn-pattern-error' : '',
    validPattern ? 'cmn-auto-refresh-hint' : '',
    'cmn-auto-refresh-status',
  ].filter(Boolean).join(' ')

  return (
    <div id="cmnContainer" style={{ display: visible ? 'block' : 'none' }}>
      <div className="cmn-view-card">
        <div className="cmn-header"><div className="cmn-title">更改电话号码服务</div><div className="cmn-desc">更换后原号码将立即失效</div></div>
        <div id="cmn-loading" className="loader" style={{ display: loading ? 'block' : 'none' }}>正在检查换号资格…</div>
        {error ? <div style={{ color: 'var(--danger)', padding: '20px' }}>{error}</div> : null}
        {data && !loading ? (
          <div id="cmn-content" style={{ display: 'block' }}>
            <div className="cmn-body">
              <div className="cmn-price-box"><div className="cmn-price-label">服务费用</div><div className="cmn-price-val">$<span id="cmn-price">{data.price}</span></div><div className="cmn-price-tip">* <UiIcon className="cmn-risk-icon" name="alert-triangle" size={16} /> 号码更换后，旧号码将立即失效且无法找回</div></div>
              <div id="numbers-section">
                <div id="initial-load-area" style={{ textAlign: 'center', padding: '10px 0 30px 0', display: (numbers.length > 0 || numbersLoading) ? 'none' : 'block' }}>
                  <button type="button" className="refresh-btn" id="initLoadBtn" onClick={onRefresh}><UiIcon className="refresh-btn-icon" name="search" /> <span>获取一组新号码</span></button>
                </div>
                <div id="num-grid-wrapper" style={{ display: (numbers.length > 0 || numbersLoading) ? 'block' : 'none' }}>
                  <div className="cmn-pattern-field">
                    <label htmlFor="cmn-pattern-input">号码模式</label>
                    <input id="cmn-pattern-input" className="cmn-pattern-input" type="text" maxLength={32} autoComplete="off" spellCheck={false} value={pattern} placeholder="例如 666 或 6[0-9]{2}" aria-describedby={describedBy} aria-invalid={patternError ? 'true' : 'false'} onChange={(event) => onPatternChange(event.target.value)} />
                    <div id="cmn-pattern-description" className="cmn-pattern-description">纯数字按原文查找，也支持安全数字模式。</div>
                    {validPattern ? (
                      <div className="cmn-auto-refresh-guidance">
                        <div id="cmn-auto-refresh-hint" className="cmn-auto-refresh-hint">长按可自动查找，最多 20 次</div>
                        {!running ? <button id="cmn-auto-refresh-start" className="cmn-auto-refresh-start" type="button" aria-label="开始自动查找号码，最多 20 次" disabled={!canRefresh || numbersLoading} onClick={onAutoRefreshStart}>开始自动查找</button> : null}
                      </div>
                    ) : null}
                    {patternError ? <div id="cmn-pattern-error" className="cmn-pattern-error" role="alert">{patternError}</div> : null}
                    <div id="cmn-auto-refresh-status" className="cmn-auto-refresh-status" role="status" aria-live="polite" aria-atomic="true">{autoRefresh.message}</div>
                  </div>
                  <div className="cmn-grid-label">选择心仪号码</div>
                  <div className={`num-grid${numbersLoading ? ' is-loading' : ''}`} id="numGrid" aria-busy={numbersLoading || undefined}>
                    {visibleNumbers.map((number) => (
                      <button key={number} type="button" className={`num-btn ${selectedNumber === number ? 'selected' : ''}`} aria-pressed={selectedNumber === number} onClick={() => onSelectNumber(number)}>
                        <span className="num-btn-label">
                          {segmentCmnCandidate(number, findCmnPatternRanges(number, pattern)).map((segment, index) => (
                            segment.highlighted ? <mark className="cmn-match" key={`${number}-${index}`}>{segment.text}</mark> : <span key={`${number}-${index}`}>{segment.text}</span>
                          ))}
                        </span>
                      </button>
                    ))}
                    {numbersLoading ? <div className="loader cmn-grid-loader">正在获取号码库…</div> : null}
                  </div>
                  <div className="cmn-actions">
                    <button
                      type="button"
                      className={`refresh-btn cmn-auto-refresh-button${running ? ' is-running' : ''}`}
                      id="refreshNumBtn"
                      disabled={!running && !canRefresh}
                      aria-busy={running || undefined}
                      aria-describedby={validPattern ? 'cmn-auto-refresh-hint cmn-auto-refresh-status' : 'cmn-auto-refresh-status'}
                      onClick={handleRefreshClick}
                      onContextMenu={handleContextMenu}
                      onPointerDown={handlePointerDown}
                      onPointerUp={handlePointerEnd}
                      onPointerCancel={handlePointerEnd}
                      onLostPointerCapture={handlePointerEnd}
                    >
                      <UiIcon className="refresh-btn-icon" name="refresh" />
                      {running ? <span className="cmn-auto-refresh-copy"><span>自动查找 {autoRefresh.attempt}/20</span><span>点击取消</span></span> : (canRefresh ? '换一批' : <span id="refresh-timer">（{cooldown}s）</span>)}
                    </button>
                    <button type="button" className="buy-btn" id="cmnBuyBtn" onClick={onSubmit}>确认支付并更换</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

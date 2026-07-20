import { useLayoutEffect, useRef } from 'react'

import type { CmnAutoRefreshState, CmnNumbersMode } from '@/hooks/useCmn'
import type { CmnCheckResponse } from '@/types'
import { findCmnPatternRanges, segmentCmnCandidate, type CmnPattern } from '@/utils/cmnPattern'
import { CmnRefreshButton } from './CmnRefreshButton'
import { UiIcon } from './UiIcon'

type CmnSectionProps = {
  readonly autoRefresh: CmnAutoRefreshState
  readonly canRefresh: boolean
  readonly cooldown: number
  readonly data: CmnCheckResponse['data'] | null
  readonly error: string
  readonly loading: boolean
  readonly numbers: string[]
  readonly numbersLoading: boolean
  readonly numbersMode: CmnNumbersMode
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

export function CmnSection({
  autoRefresh,
  canRefresh,
  cooldown,
  data,
  error,
  loading,
  numbers,
  numbersLoading,
  numbersMode,
  onAutoRefreshCancel,
  onAutoRefreshStart,
  onPatternChange,
  onRefresh,
  onSelectNumber,
  onSubmit,
  parsedPattern,
  pattern,
  selectedNumber,
  visible,
}: CmnSectionProps): JSX.Element {
  const keyboardStartPendingRef = useRef(false)
  const visibleNumbers = numbers.slice(0, 9)
  const patternError = parsedPattern.kind === 'invalid' ? parsedPattern.message : ''
  const validPattern = parsedPattern.kind === 'literal' || parsedPattern.kind === 'regex'

  const handleAutoRefreshStartClick = (event: React.MouseEvent<HTMLButtonElement>): void => {
    keyboardStartPendingRef.current = event.detail === 0
    onAutoRefreshStart()
    window.setTimeout(() => {
      keyboardStartPendingRef.current = false
    }, 0)
  }

  useLayoutEffect(() => {
    if (!keyboardStartPendingRef.current || autoRefresh.kind !== 'running') return
    keyboardStartPendingRef.current = false
    document.getElementById('refreshNumBtn')?.focus()
  }, [autoRefresh.kind])

  const renderRefreshButton = (mode: CmnNumbersMode): JSX.Element => (
    <CmnRefreshButton
      autoRefresh={autoRefresh}
      canRefresh={canRefresh}
      cooldown={cooldown}
      mode={mode}
      numbersLoading={numbersLoading}
      onAutoRefreshCancel={onAutoRefreshCancel}
      onAutoRefreshStart={onAutoRefreshStart}
      onRefresh={onRefresh}
      pattern={pattern}
      validPattern={validPattern}
      visible={visible}
    />
  )

  const describedBy = [
    'cmn-pattern-description',
    patternError ? 'cmn-pattern-error' : '',
    validPattern ? 'cmn-auto-refresh-hint' : '',
    'cmn-auto-refresh-status',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div id="cmnContainer" style={{ display: visible ? 'block' : 'none' }}>
      <div className="cmn-view-card">
        <div className="cmn-header">
          <div className="cmn-title">更改电话号码服务</div>
          <div className="cmn-desc">更换后原号码将立即失效</div>
        </div>
        <div id="cmn-loading" className="loader" style={{ display: loading ? 'block' : 'none' }}>
          正在检查换号资格…
        </div>
        {error ? <div style={{ color: 'var(--danger)', padding: '20px' }}>{error}</div> : null}
        {data && !loading ? (
          <div id="cmn-content" style={{ display: 'block' }}>
            <div className="cmn-body">
              <div className="cmn-price-box">
                <div className="cmn-price-label">服务费用</div>
                <div className="cmn-price-val">
                  $<span id="cmn-price">{data.price}</span>
                </div>
                <div className="cmn-price-tip">
                  * <UiIcon className="cmn-risk-icon" name="alert-triangle" size={16} />{' '}
                  号码更换后，旧号码将立即失效且无法找回
                </div>
              </div>
              <div id="numbers-section">
                <div
                  id="initial-load-area"
                  style={{
                    textAlign: 'center',
                    padding: '10px 0 30px 0',
                    display: numbersMode === 'initial' ? 'block' : 'none',
                  }}
                >
                  {renderRefreshButton('initial')}
                </div>
                <div id="num-grid-wrapper" style={{ display: numbersMode === 'subsequent' ? 'block' : 'none' }}>
                  <div className="cmn-pattern-field">
                    <label htmlFor="cmn-pattern-input">号码模式</label>
                    <input
                      id="cmn-pattern-input"
                      className="cmn-pattern-input"
                      type="text"
                      maxLength={32}
                      autoComplete="off"
                      spellCheck={false}
                      value={pattern}
                      placeholder="例如 666 或 6[0-9]{2}"
                      aria-describedby={describedBy}
                      aria-invalid={patternError ? 'true' : 'false'}
                      onChange={(event) => onPatternChange(event.target.value)}
                    />
                    <div id="cmn-pattern-description" className="cmn-pattern-description">
                      纯数字按原文查找，也支持安全数字模式。
                    </div>
                    {validPattern ? (
                      <div className="cmn-auto-refresh-guidance">
                        <div id="cmn-auto-refresh-hint" className="cmn-auto-refresh-hint">
                          长按可自动查找，最多 20 次
                        </div>
                        {autoRefresh.kind === 'running' ? null : (
                          <button
                            id="cmn-auto-refresh-start"
                            className="cmn-auto-refresh-start"
                            type="button"
                            aria-label="开始自动查找号码，最多 20 次"
                            disabled={!canRefresh || numbersLoading}
                            onClick={handleAutoRefreshStartClick}
                          >
                            开始自动查找
                          </button>
                        )}
                      </div>
                    ) : null}
                    {patternError ? (
                      <div id="cmn-pattern-error" className="cmn-pattern-error" role="alert">
                        {patternError}
                      </div>
                    ) : null}
                    <div
                      id="cmn-auto-refresh-status"
                      className="cmn-auto-refresh-status"
                      role="status"
                      aria-live="polite"
                      aria-atomic="true"
                    >
                      {autoRefresh.message}
                    </div>
                  </div>
                  <div className="cmn-grid-label">选择心仪号码</div>
                  <div
                    className={`num-grid${numbersLoading ? ' is-loading' : ''}`}
                    id="numGrid"
                    aria-busy={numbersLoading || undefined}
                  >
                    {visibleNumbers.map((number) => (
                      <button
                        key={number}
                        type="button"
                        className={`num-btn ${selectedNumber === number ? 'selected' : ''}`}
                        aria-pressed={selectedNumber === number}
                        onClick={() => onSelectNumber(number)}
                      >
                        <span className="num-btn-label">
                          {segmentCmnCandidate(number, findCmnPatternRanges(number, pattern)).map((segment, index) =>
                            segment.highlighted ? (
                              <mark className="cmn-match" key={`${number}-${index}`}>
                                {segment.text}
                              </mark>
                            ) : (
                              <span key={`${number}-${index}`}>{segment.text}</span>
                            ),
                          )}
                        </span>
                      </button>
                    ))}
                    {numbersLoading ? <div className="loader cmn-grid-loader">正在获取号码库…</div> : null}
                  </div>
                  <div className="cmn-actions">
                    {renderRefreshButton('subsequent')}
                    <button type="button" className="buy-btn" id="cmnBuyBtn" onClick={onSubmit}>
                      确认支付并更换
                    </button>
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

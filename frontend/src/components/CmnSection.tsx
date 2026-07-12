import type { CmnCheckResponse } from '../types'
import { findCmnPatternRanges, segmentCmnCandidate, type CmnPattern } from '../utils/cmnPattern'
import { UiIcon } from './UiIcon'

type CmnSectionProps = {
  readonly canRefresh: boolean
  readonly cooldown: number
  readonly data: CmnCheckResponse['data'] | null
  readonly error: string
  readonly loading: boolean
  readonly numbers: string[]
  readonly numbersLoading: boolean
  readonly onPatternChange: (pattern: string) => void
  readonly onRefresh: () => void
  readonly onSelectNumber: (number: string) => void
  readonly onSubmit: () => void
  readonly parsedPattern: CmnPattern
  readonly pattern: string
  readonly selectedNumber: string | null
  readonly visible: boolean
}

export function CmnSection({ canRefresh, cooldown, data, error, loading, numbers, numbersLoading, onPatternChange, onRefresh, onSelectNumber, onSubmit, parsedPattern, pattern, selectedNumber, visible }: CmnSectionProps): JSX.Element {
  const visibleNumbers = numbers.slice(0, 9)
  const patternError = parsedPattern.kind === 'invalid' ? parsedPattern.message : ''
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
                  <button className="refresh-btn" id="initLoadBtn" onClick={onRefresh}><UiIcon className="refresh-btn-icon" name="search" /> <span>获取一组新号码</span></button>
                </div>
                <div id="num-grid-wrapper" style={{ display: (numbers.length > 0 || numbersLoading) ? 'block' : 'none' }}>
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
                      aria-describedby={patternError ? 'cmn-pattern-description cmn-pattern-error' : 'cmn-pattern-description'}
                      aria-invalid={patternError ? 'true' : 'false'}
                      onChange={(event) => onPatternChange(event.target.value)}
                    />
                    <div id="cmn-pattern-description" className="cmn-pattern-description">纯数字按原文查找，也支持安全数字模式。</div>
                    {patternError ? <div id="cmn-pattern-error" className="cmn-pattern-error" role="alert">{patternError}</div> : null}
                  </div>
                  <div className="cmn-grid-label">选择心仪号码</div>
                  <div className="num-grid" id="numGrid">
                    {numbersLoading ? <div className="loader" style={{ gridColumn: 'span 3', padding: '20px' }}>正在获取号码库…</div> : visibleNumbers.map((number) => (
                      <button key={number} type="button" className={`num-btn ${selectedNumber === number ? 'selected' : ''}`} aria-pressed={selectedNumber === number} onClick={() => onSelectNumber(number)}>
                        <span className="num-btn-label">
                          {segmentCmnCandidate(number, findCmnPatternRanges(number, pattern)).map((segment, index) => (
                            segment.highlighted ? <mark className="cmn-match" key={`${number}-${index}`}>{segment.text}</mark> : <span key={`${number}-${index}`}>{segment.text}</span>
                          ))}
                        </span>
                      </button>
                    ))}
                  </div>
                  <div className="cmn-actions">
                    <button className="refresh-btn" id="refreshNumBtn" disabled={!canRefresh} onClick={onRefresh}><UiIcon className="refresh-btn-icon" name="refresh" /> {canRefresh ? '换一批' : <span id="refresh-timer">（{cooldown}s）</span>}</button>
                    <button className="buy-btn" id="cmnBuyBtn" onClick={onSubmit}>确认支付并更换</button>
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

import type { CmnCheckResponse } from '../types'

type CmnSectionProps = {
  readonly canRefresh: boolean
  readonly cooldown: number
  readonly data: CmnCheckResponse['data'] | null
  readonly error: string
  readonly loading: boolean
  readonly numbers: string[]
  readonly numbersLoading: boolean
  readonly onClearLongPress: () => void
  readonly onRefresh: () => void
  readonly onSelectNumber: (number: string) => void
  readonly onStartLongPress: (number: string) => void
  readonly onSubmit: () => void
  readonly selectedNumber: string | null
  readonly visible: boolean
}

export function CmnSection({ canRefresh, cooldown, data, error, loading, numbers, numbersLoading, onClearLongPress, onRefresh, onSelectNumber, onStartLongPress, onSubmit, selectedNumber, visible }: CmnSectionProps): JSX.Element {
  const visibleNumbers = numbers.slice(0, 9)
  return (
    <div id="cmnContainer" style={{ display: visible ? 'block' : 'none' }}>
      <div className="cmn-view-card">
        <div className="cmn-header"><div className="cmn-title">更改电话号码服务</div><div className="cmn-desc">更换后原号码将立即失效</div></div>
        <div id="cmn-loading" className="loader" style={{ display: loading ? 'block' : 'none' }}>正在检查换号资格...</div>
        {error ? <div style={{ color: 'var(--danger)', padding: '20px' }}>{error}</div> : null}
        {data && !loading ? (
          <div id="cmn-content" style={{ display: 'block' }}>
            <div className="cmn-body">
              <div className="cmn-price-box"><div className="cmn-price-label">服务费用</div><div className="cmn-price-val">$<span id="cmn-price">{data.price}</span></div><div className="cmn-price-tip">* ⚠️ 号码更换后，旧号码将立即失效且无法找回</div></div>
              <div id="numbers-section">
                <div id="initial-load-area" style={{ textAlign: 'center', padding: '10px 0 30px 0', display: (numbers.length > 0 || numbersLoading) ? 'none' : 'block' }}>
                  <button className="refresh-btn" id="initLoadBtn" onClick={onRefresh}><span>🔍</span> <span>获取一组新号码</span></button>
                </div>
                <div id="num-grid-wrapper" style={{ display: (numbers.length > 0 || numbersLoading) ? 'block' : 'none' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-sub)', marginBottom: '10px', display: 'flex', justifyContent: 'space-between' }}><span>选择心仪号码</span><span>长按可手填</span></div>
                  <div className="num-grid" id="numGrid">
                    {numbersLoading ? <div className="loader" style={{ gridColumn: 'span 3', padding: '20px' }}>正在获取号码库...</div> : visibleNumbers.map((number) => (
                      <div key={number} className={`num-btn ${selectedNumber === number ? 'selected' : ''}`} onClick={() => onSelectNumber(number)} onMouseDown={() => onStartLongPress(number)} onTouchStart={() => onStartLongPress(number)} onMouseUp={onClearLongPress} onMouseLeave={onClearLongPress} onTouchEnd={onClearLongPress} onTouchMove={onClearLongPress}>{number}</div>
                    ))}
                  </div>
                  <div className="cmn-actions">
                    <button className="refresh-btn" id="refreshNumBtn" disabled={!canRefresh} onClick={onRefresh}>{canRefresh ? '🔄 换一批' : `⏳ (`}<span id="refresh-timer">{canRefresh ? '' : `${cooldown}s`}</span>{canRefresh ? '' : ')'}</button>
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

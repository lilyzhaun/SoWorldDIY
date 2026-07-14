import { LoginSuccessStatus } from '@/components/LoginSuccessStatus'
import { StatusMessage } from '@/components/StatusMessage'
import { LOGIN_REDIRECT_DELAY_MS, useLoginFlow } from '@/hooks/useLoginFlow'

export function LoginPage(): JSX.Element {
  const {
    authCode,
    clearRetainedToastIfHidden,
    handleSendOtp,
    handleSubmit,
    identifier,
    isAddMode,
    loginSucceeded,
    otp,
    otpBusy,
    otpLabel,
    password,
    retainedToast,
    setAuthCode,
    setIdentifier,
    setOtp,
    setPassword,
    setTab,
    submitBusy,
    tab,
    toast,
  } = useLoginFlow()

  return (
    <>
      <div className="login-brand-panel">
        <h1>
          Welcome to
          <br />
          <span>3HK</span> Assistant
        </h1>
        <p>
          DIY / SoSIM / SIMWorld / 3國際萬能卡 / <span className="brand-nowrap-token">HAHA SIM</span> 套餐管理工具
        </p>
        <div className="login-brand-features">
          <div className="feat">
            <div className="feat-dot"></div>多品牌账号统一管理
          </div>
          <div className="feat">
            <div className="feat-dot"></div>套餐浏览与一键购买
          </div>
          <div className="feat">
            <div className="feat-dot"></div>余额查询与充值跳转
          </div>
          <div className="feat">
            <div className="feat-dot"></div>资源互转与换号服务
          </div>
        </div>
      </div>
      <div className="main-wrapper">
        <div className="auth-card">
          <div className="header">
            <h2>{isAddMode ? '添加新账号' : '3HK 助手'}</h2>
            <p>
              支持 DIY / SoSIM / SIMWorld
              <br />
              3國際萬能卡 / <span className="brand-nowrap-token">HAHA SIM</span>
            </p>
          </div>

          <div className="tabs">
            <button
              type="button"
              className={`tab${tab === 'password' ? ' active' : ''}`}
              aria-pressed={tab === 'password'}
              onClick={() => setTab('password')}
            >
              密码登录
            </button>
            <button
              type="button"
              className={`tab${tab === 'otp' ? ' active' : ''}`}
              aria-pressed={tab === 'otp'}
              onClick={() => setTab('otp')}
            >
              验证码登录
            </button>
          </div>

          <form id="loginForm" onSubmit={(event) => void handleSubmit(event)}>
            <input type="hidden" id="login_type" name="login_type" value={tab} />

            <div className="form-group">
              <label className="input-label">账号 (手机号/邮箱)</label>
              <input
                type="text"
                id="identifier"
                name="identifier"
                placeholder="请输入您的账号"
                required
                autoComplete="username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </div>

            <div
              className="form-group"
              id="password-group"
              style={{ display: tab === 'password' ? undefined : 'none' }}
            >
              <label className="input-label">登录密码</label>
              <input
                type="password"
                name="password"
                placeholder="请输入密码"
                autoComplete="current-password"
                required={tab === 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <div className="form-group" id="otp-group" style={{ display: tab === 'otp' ? undefined : 'none' }}>
              <label className="input-label">验证码</label>
              <div className="otp-group">
                <input
                  type="number"
                  name="otp"
                  placeholder="6位验证码"
                  autoComplete="one-time-code"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                />
                <button
                  type="button"
                  className="otp-btn"
                  id="sendOtpBtn"
                  onClick={() => void handleSendOtp()}
                  disabled={otpBusy}
                >
                  {otpLabel}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label className="input-label">系统鉴权码</label>
              <input
                type="text"
                name="auth_code"
                placeholder="联系管理员获取"
                required
                autoComplete="off"
                value={authCode}
                onChange={(e) => setAuthCode(e.target.value)}
              />
            </div>

            <button type="submit" className="submit-btn" id="submitBtn" disabled={submitBusy}>
              {submitBusy ? '正在登录…' : isAddMode ? '登录并添加' : '立即登录'}
            </button>
          </form>
        </div>
      </div>

      <div className="footer-note">
        仅供个人学习使用，高净值账号请勿使用本网站。
        <br />
        <span>
          如使用密码登录请于24h内更改密码。
          <br />
          发生一切损失于本网站无关。
        </span>
        <br />
        <a
          href="https://example.invalid/support"
          target="_blank"
          rel="noopener noreferrer"
          className="support-link"
          aria-label="联系 external_delivery 客服"
        >
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 11.944 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
          </svg>
        </a>
      </div>

      <div
        className={`toast${toast ? ' show' : ''}`}
        id="toast"
        onTransitionEnd={(event) => clearRetainedToastIfHidden(event.propertyName)}
      >
        {retainedToast ? <StatusMessage message={retainedToast.message} tone={retainedToast.tone} /> : null}
      </div>
      {loginSucceeded ? <LoginSuccessStatus durationMs={LOGIN_REDIRECT_DELAY_MS} /> : null}
    </>
  )
}

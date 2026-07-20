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

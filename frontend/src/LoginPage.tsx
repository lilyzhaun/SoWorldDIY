import { useEffect, useState } from 'react'

import { apiFetch, apiPostJson } from './api/client'
import { toErrorMessage } from './utils'

type TabType = 'password' | 'otp'

export function LoginPage(): JSX.Element {
  const [tab, setTab] = useState<TabType>('password')
  const [isAddMode, setIsAddMode] = useState(false)
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [authCode, setAuthCode] = useState('')
  const [toast, setToast] = useState('')
  const [otpBusy, setOtpBusy] = useState(false)
  const [otpLabel, setOtpLabel] = useState('获取验证码')
  const [submitBusy, setSubmitBusy] = useState(false)

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    setIsAddMode(urlParams.get('add') === '1')
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => {
      setToast('')
    }, 3000)
    return () => window.clearTimeout(timer)
  }, [toast])

  const handleSendOtp = async (): Promise<void> => {
    if (!identifier.trim()) {
      setToast('请先输入账号')
      return
    }
    if (!authCode.trim()) {
      setToast('请先输入鉴权码')
      return
    }

    setOtpBusy(true)
    setOtpLabel('发送中...')
    try {
      const data = await apiPostJson<{ status?: string; message?: string }>('/api/send-otp', { identifier: identifier.trim(), auth_code: authCode.trim() })
      if (data.status !== 'success') {
        throw new Error(data.message ?? '验证码发送失败')
      }

      setToast('✅ 验证码已发送')
      let countdown = 60
      setOtpLabel(`${countdown}s 后重试`)
      const timer = window.setInterval(() => {
        countdown -= 1
        if (countdown < 0) {
          window.clearInterval(timer)
          setOtpBusy(false)
          setOtpLabel('获取验证码')
        } else {
          setOtpLabel(`${countdown}s 后重试`)
        }
      }, 1000)
    } catch (error: unknown) {
      setOtpBusy(false)
      setOtpLabel('获取验证码')
      setToast(`❌ ${toErrorMessage(error)}`)
    }
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    setSubmitBusy(true)

    try {
      const formData = new FormData()
      formData.append('login_type', tab)
      formData.append('identifier', identifier)
      formData.append('auth_code', authCode)
      if (tab === 'password') {
        formData.append('password', password)
      } else {
        formData.append('otp', otp)
      }

      const response = await apiFetch('/login', { method: 'POST', body: formData })
      if (response.status === 401) {
        const errData = (await response.json()) as { message?: string }
        throw new Error(errData.message ?? '认证失败')
      }

      const data = (await response.json()) as { status?: string; message?: string; redirect?: string }
      if (data.status !== 'success') {
        throw new Error(data.message ?? '登录失败')
      }

      setToast('🎉 登录成功')
      window.setTimeout(() => {
        window.location.href = data.redirect ?? '/main'
      }, 800)
    } catch (error: unknown) {
      setToast(`⚠️ ${toErrorMessage(error)}`)
      setSubmitBusy(false)
    }
  }

  return (
    <>
      <div className="login-brand-panel">
        <h1>Welcome to<br /><span>3HK</span> Assistant</h1>
        <p>DIY / SoSIM / SIMWorld / 3國際萬能卡 / HAHA SIM 套餐管理工具</p>
        <div className="login-brand-features">
          <div className="feat"><div className="feat-dot"></div>多品牌账号统一管理</div>
          <div className="feat"><div className="feat-dot"></div>套餐浏览与一键购买</div>
          <div className="feat"><div className="feat-dot"></div>余额查询与充值跳转</div>
          <div className="feat"><div className="feat-dot"></div>资源互转与换号服务</div>
        </div>
      </div>
      <div className="main-wrapper">
        <div className="auth-card">
          <div className="header">
            <h2>{isAddMode ? '添加新账号' : '3HK 助手'}</h2>
            <p>
              支持 DIY / SoSIM / SIMWorld<br />
              3國際萬能卡 / HAHA SIM
            </p>
          </div>

          <div className="tabs">
            <div
              className={`tab${tab === 'password' ? ' active' : ''}`}
              onClick={() => setTab('password')}
            >
              密码登录
            </div>
            <div
              className={`tab${tab === 'otp' ? ' active' : ''}`}
              onClick={() => setTab('otp')}
            >
              验证码登录
            </div>
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

            <div
              className="form-group"
              id="otp-group"
              style={{ display: tab === 'otp' ? undefined : 'none' }}
            >
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
              {submitBusy ? '正在登录...' : isAddMode ? '登录并添加' : '立即登录'}
            </button>
          </form>
        </div>
      </div>

      <div className="footer-note">
        仅供个人学习使用，高净值账号请勿使用本网站。<br />
        <span>
          如使用密码登录请于24h内更改密码。<br />
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

      <div className={`toast${toast ? ' show' : ''}`} id="toast">{toast}</div>
    </>
  )
}

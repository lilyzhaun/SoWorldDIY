import { useEffect, useState } from 'react'

import { apiFetch, apiPostJson } from '@/api/client'
import type { StatusTone } from '@/components/StatusMessage'
import { toErrorMessage } from '@/utils'

export type LoginTab = 'password' | 'otp'
export type LoginToastState = { readonly message: string; readonly tone: StatusTone }

export const LOGIN_REDIRECT_DELAY_MS = 800

export function useLoginFlow() {
  const [tab, setTab] = useState<LoginTab>('password')
  const [isAddMode, setIsAddMode] = useState(false)
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [authCode, setAuthCode] = useState('')
  const [toast, setToast] = useState<LoginToastState | null>(null)
  const [retainedToast, setRetainedToast] = useState<LoginToastState | null>(null)
  const [otpBusy, setOtpBusy] = useState(false)
  const [otpLabel, setOtpLabel] = useState('获取验证码')
  const [submitBusy, setSubmitBusy] = useState(false)
  const [loginSucceeded, setLoginSucceeded] = useState(false)

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    setIsAddMode(urlParams.get('add') === '1')
    if (urlParams.get('session') === 'expired') {
      const message: LoginToastState = { message: '会话已变更或失效，请重新登录', tone: 'warning' }
      setToast(message)
      setRetainedToast(message)
    }
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => {
      setToast(null)
    }, 3000)
    return () => window.clearTimeout(timer)
  }, [toast])

  const presentToast = (nextToast: LoginToastState): void => {
    setRetainedToast(nextToast)
    setToast(nextToast)
  }

  const clearRetainedToastIfHidden = (propertyName: string): void => {
    if (!toast && propertyName === 'opacity') setRetainedToast(null)
  }

  const handleSendOtp = async (): Promise<void> => {
    if (!identifier.trim()) {
      presentToast({ message: '请先输入账号', tone: 'warning' })
      return
    }
    if (!authCode.trim()) {
      presentToast({ message: '请先输入鉴权码', tone: 'warning' })
      return
    }

    setOtpBusy(true)
    setOtpLabel('发送中…')
    try {
      const data = await apiPostJson<{ status?: string; message?: string }>('/api/send-otp', {
        identifier: identifier.trim(),
        auth_code: authCode.trim(),
      })
      if (data.status !== 'success') {
        throw new Error(data.message ?? '验证码发送失败')
      }

      presentToast({ message: '验证码已发送', tone: 'success' })
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
      presentToast({ message: toErrorMessage(error), tone: 'error' })
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

      setToast(null)
      setLoginSucceeded(true)
      window.setTimeout(() => {
        window.location.href = data.redirect ?? '/main'
      }, LOGIN_REDIRECT_DELAY_MS)
    } catch (error: unknown) {
      presentToast({ message: toErrorMessage(error), tone: 'warning' })
      setSubmitBusy(false)
    }
  }

  return {
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
  }
}

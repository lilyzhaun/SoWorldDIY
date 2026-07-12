import { describe, expect, it } from 'vitest'

import loginPageSource from './LoginPage.tsx?raw'
import mainPageSource from './MainPage.tsx?raw'
import transferSource from './hooks/useTransfer.ts?raw'

describe('semantic feedback flow contracts', () => {
  it('uses typed login toast tones, plain messages, and unchanged timing contracts', () => {
    expect(loginPageSource).toContain("import { StatusMessage, type StatusTone } from './components/StatusMessage'")
    expect(loginPageSource).toContain('readonly tone: StatusTone')
    expect(loginPageSource).toContain("presentToast({ message: '验证码已发送', tone: 'success' })")
    expect(loginPageSource).toContain("presentToast({ message: toErrorMessage(error), tone: 'error' })")
    expect(loginPageSource).toContain("presentToast({ message: toErrorMessage(error), tone: 'warning' })")
    expect(loginPageSource).toContain('<StatusMessage message={retainedToast.message} tone={retainedToast.tone} />')
    expect(loginPageSource).toContain('}, 3000)')
    expect(loginPageSource).toContain('let countdown = 60')
    expect(loginPageSource).toContain('const LOGIN_REDIRECT_DELAY_MS = 800')
    for (const emoji of ['✅', '❌', '⚠️']) {
      expect(loginPageSource).not.toContain(emoji)
    }
  })

  it('keeps transfer validation and failure messages exact without embedded emoji', () => {
    for (const message of [
      '请输入有效的手机号码',
      '请输入转移数量',
      '转移数量不能少于 ${transferDraft.minTransfer}',
      '余额不足',
      "data.message || '转移失败'",
      '网络请求失败',
    ]) {
      expect(transferSource).toContain(message)
    }
    for (const emoji of ['✅', '❌', '⚠️']) {
      expect(transferSource).not.toContain(emoji)
    }
  })

  it('passes a plain transfer-success message through the alert success tone', () => {
    expect(mainPageSource).toContain("type AlertState = { readonly text: string; readonly tone?: StatusTone }")
    expect(mainPageSource).toContain("showAlert(`资源已成功转移给 ${target}`, '办理成功', 'success')")
    expect(mainPageSource).toContain('<StatusMessage message={alert.text} tone={alert.tone} />')
    expect(mainPageSource).not.toContain('✅ 资源已成功转移给')
  })

  it('uses the single-character ellipsis in touched user-visible loading labels', () => {
    expect(loginPageSource).toContain("setOtpLabel('发送中…')")
    expect(loginPageSource).toContain("submitBusy ? '正在登录…'")
    expect(mainPageSource).toContain("purchaseDraft?.submitting ? '提交中…'")
    expect(mainPageSource).toContain("transferSubmitting ? '处理中…'")
    expect(mainPageSource).toContain('正在同步账户信息…')
  })
})

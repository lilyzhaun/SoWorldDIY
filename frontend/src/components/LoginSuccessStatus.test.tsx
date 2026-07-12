import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { LoginSuccessStatus } from './LoginSuccessStatus'

describe('LoginSuccessStatus', () => {
  it('renders an accessible success status with redirect progress', () => {
    const html = renderToStaticMarkup(<LoginSuccessStatus durationMs={800} />)

    expect(html).toContain('role="status"')
    expect(html).toContain('aria-live="polite"')
    expect(html).toContain('aria-atomic="true"')
    expect(html).toContain('>登录成功<')
    expect(html).toContain('>正在进入控制台<')
    expect(html).toContain('<svg')
    expect(html).toContain('aria-hidden="true"')
    expect(html).toContain('focusable="false"')
    expect(html).not.toContain('🎉')
    expect(html).toContain('class="login-success-progress" aria-hidden="true"')
    expect(html).toContain('class="login-success-progress-fill" style="animation-duration:800ms"')
  })
})

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import activeOffersSource from './components/ActiveOffersSection.tsx?raw'
import dialogHookSource from './hooks/useDialogAccessibility.ts?raw'
import loginPageSource from './LoginPage.tsx?raw'

const mainStyles = readFileSync(fileURLToPath(new globalThis.URL('./styles/main.css', import.meta.url)), 'utf8')
const loginStyles = readFileSync(fileURLToPath(new globalThis.URL('./styles/login.css', import.meta.url)), 'utf8')

describe('visual QA blocking contracts', () => {
  it('uses theme tokens for dark-mode-sensitive quantity controls', () => {
    expect(mainStyles).toContain('.qty-btn')
    expect(mainStyles).toContain('background: var(--bg-card)')
    expect(mainStyles).toContain('.cart-mini-btn')
    expect(mainStyles).not.toMatch(/\.qty-btn\s*\{[^}]*background:\s*white/s)
    expect(mainStyles).not.toMatch(/\.cart-mini-btn\s*\{[^}]*background:\s*white/s)
  })

  it('defines semantic account status tones in light and dark themes', () => {
    for (const tone of ['active', 'preactive', 'suspended', 'unknown']) {
      expect(mainStyles).toContain(`--account-${tone}`)
      expect(mainStyles).toContain(`.tone-${tone}`)
    }
    expect(mainStyles).toContain('color: currentColor')
  })

  it('disables spinner rotation and completes progress under reduced motion', () => {
    expect(mainStyles).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*\.spinner\s*\{[^}]*animation:\s*none !important/s)
    expect(loginStyles).toMatch(/\.login-success-progress-fill\s*\{[^}]*animation:\s*none[^}]*transform:\s*scaleX\(1\)/s)
  })

  it('uses one 240ms modal exit contract and standard motion durations', () => {
    expect(mainStyles).toContain('opacity var(--motion-slow)')
    expect(mainStyles).toContain('transform var(--motion-slow)')
    expect(mainStyles).not.toContain('transform 220ms')
    expect(mainStyles).not.toContain('0.2s')
    expect(loginStyles).toContain('animation: loginSuccessEnter var(--motion-base)')
    expect(loginStyles).not.toContain('loginSuccessEnter 160ms')
  })

  it('keeps inbox controls separated and exposes robust dialog focus lifecycle', () => {
    expect(mainStyles).toMatch(/\.modal-icon-btn\s*\{[^}]*width:\s*40px[^}]*height:\s*40px/s)
    expect(mainStyles).not.toMatch(/\.modal-icon-btn\s*\{[^}]*margin:\s*-\d/s)
    expect(dialogHookSource).toContain("event.key === 'Escape'")
    expect(dialogHookSource).toContain('.focus()')
    expect(dialogHookSource).toContain('previouslyFocused')
  })

  it('retains toast content for its visual exit without changing the three-second timer', () => {
    expect(loginPageSource).toContain('retainedToast')
    expect(loginPageSource).toContain('}, 3000)')
    expect(loginPageSource).toContain('onTransitionEnd')
  })

  it('keeps required labels and avoids legacy transfer abbreviation', () => {
    expect(activeOffersSource).toContain('>转移</button>')
    expect(activeOffersSource).not.toContain('>转</button>')
  })
})

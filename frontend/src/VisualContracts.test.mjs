import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import activeOffersSource from './components/ActiveOffersSection.tsx?raw'
import dialogHookSource from './hooks/useDialogAccessibility.ts?raw'
import historyModalSource from './components/HistoryModal.tsx?raw'
import loginPageSource from './LoginPage.tsx?raw'
import sanitizeInboxSource from './utils/sanitizeInboxContent.ts?raw'

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

  it('uses one 240ms generic modal exit contract and calm record/cart motion', () => {
    expect(mainStyles).toContain('opacity var(--motion-slow)')
    expect(mainStyles).toContain('transform var(--motion-slow)')
    expect(mainStyles).toContain('--motion-calm: 150ms')
    expect(mainStyles).toMatch(/\.records-modal-box\s*\{[^}]*transition:\s*opacity var\(--motion-calm\)/s)
    expect(mainStyles).toMatch(/#cartQuantityModal \.modal-box\s*\{[^}]*transform:\s*none[^}]*transition:\s*opacity var\(--motion-fast\)/s)
    expect(mainStyles).not.toContain('transform 220ms')
    expect(mainStyles).not.toContain('0.2s')
    expect(loginStyles).toContain('animation: loginSuccessEnter var(--motion-base)')
    expect(loginStyles).not.toContain('loginSuccessEnter 160ms')
  })

  it('removes bouncy transforms from plan and cart controls', () => {
    expect(mainStyles).not.toMatch(/\.plan-card[^{}]*\{[^}]*transition:[^;}]*transform/s)
    expect(mainStyles).not.toMatch(/\.plan-card:hover\s*\{[^}]*transform/s)
    expect(mainStyles).not.toMatch(/\.plan-card:active\s*\{[^}]*transform/s)
    for (const selector of ['buy-btn', 'cart-fab', 'qty-btn', 'cart-mini-btn']) {
      expect(mainStyles).not.toMatch(new RegExp(`\\.${selector}[^{}]*\\{[^}]*transition:[^;}]*transform`, 's'))
      expect(mainStyles).not.toMatch(new RegExp(`\\.${selector}:active[^{}]*\\{[^}]*transform`, 's'))
    }
    expect(mainStyles).toMatch(/\.card-details\s*\{[^}]*var\(--motion-calm\)/s)
    expect(mainStyles).toMatch(/\.arrow\s*\{[^}]*var\(--motion-calm\)/s)
  })

  it('defines responsive token-driven record modal structure', () => {
    expect(mainStyles).toMatch(/\.records-modal-overlay\s*\{[^}]*padding:[^;}]*env\(safe-area-inset/s)
    expect(mainStyles).toMatch(/\.records-modal-box\s*\{[^}]*width:\s*calc\(100vw - 24px\)[^}]*border-radius:\s*18px/s)
    expect(mainStyles).toMatch(/\.records-modal-header\s*\{[^}]*position:\s*sticky/s)
    expect(mainStyles).toMatch(/\.records-modal-content\s*\{[^}]*overflow-y:\s*auto/s)
    expect(mainStyles).toMatch(/\.records-back-btn\s*\{[^}]*appearance:\s*none[^}]*width:\s*40px[^}]*height:\s*40px/s)
    expect(mainStyles).not.toContain('transition: all')
  })

  it('keeps record detail prose readable for CJK and constrains rich media', () => {
    expect(mainStyles).toMatch(/\.inbox-detail\s*\{[^}]*text-wrap:\s*pretty[^}]*line-break:\s*strict[^}]*overflow-wrap:\s*break-word/s)
    expect(mainStyles).toMatch(/\.inbox-detail\s+(?:a|code)[^}]*\{[^}]*overflow-wrap:\s*anywhere/s)
    expect(mainStyles).toMatch(/\.inbox-detail\s+img\s*\{[^}]*max-width:\s*100%[^}]*height:\s*auto/s)
    expect(mainStyles).not.toMatch(/\.inbox-detail\s*\{[^}]*overflow-wrap:\s*anywhere/s)
    expect(mainStyles).toMatch(/\.inbox-detail\s*\{[^}]*word-break:\s*normal[^}]*line-break:\s*strict[^}]*overflow-wrap:\s*break-word/s)
    expect(mainStyles).toMatch(/@supports \(word-break: auto-phrase\)\s*\{[^}]*\.inbox-detail\s*\{[^}]*word-break:\s*auto-phrase/s)
  })

  it('wraps sanitized inbox time tokens through text-node traversal only', () => {
    expect(sanitizeInboxSource).toContain('DOMPurify.sanitize')
    expect(sanitizeInboxSource).toContain('createTreeWalker')
    expect(sanitizeInboxSource).toContain('NodeFilter.SHOW_TEXT')
    expect(sanitizeInboxSource).toContain('inbox-nowrap-token')
    expect(mainStyles).toMatch(/\.inbox-nowrap-token\s*\{[^}]*white-space:\s*nowrap/s)
  })

  it('reserves anywhere wrapping for technical history tokens', () => {
    expect(mainStyles).toMatch(/\.records-detail-list dd\s*\{[^}]*overflow-wrap:\s*break-word[^}]*line-break:\s*strict[^}]*word-break:\s*normal/s)
    expect(mainStyles).not.toMatch(/\.records-detail-list dd\s*\{[^}]*overflow-wrap:\s*anywhere/s)
    expect(mainStyles).toMatch(/\.records-technical-token\s*\{[^}]*overflow-wrap:\s*anywhere/s)
    expect(historyModalSource).toContain('<dd className="records-technical-token">{detailOrder}</dd>')
  })

  it('stacks mobile record details and balances inbox prose without overflow', () => {
    expect(mainStyles).toMatch(/@media \(max-width: 480px\)[\s\S]*\.records-detail-list > div\s*\{[^}]*grid-template-columns:\s*1fr/s)
    expect(mainStyles).toMatch(/@media \(max-width: 480px\)[\s\S]*\.records-detail-list dd\s*\{[^}]*text-align:\s*left/s)
    expect(mainStyles).toMatch(/@media \(max-width: 480px\)[\s\S]*\.records-detail-content\s*\{[^}]*padding:\s*8px/s)
    expect(mainStyles).toMatch(/@media \(max-width: 480px\)[\s\S]*\.records-detail-surface\s*\{[^}]*max-width:\s*100%[^}]*padding:\s*12px/s)
    expect(mainStyles).toMatch(/@media \(max-width: 480px\)[\s\S]*\.inbox-detail (?:p|li)[^}]*\{[^}]*text-wrap:\s*balance/s)
  })

  it('uses a scoped accessible history query treatment without disabled opacity', () => {
    expect(mainStyles).toContain('--records-query-bg: #C05200')
    expect(mainStyles).toMatch(/\.filter-btn\s*\{[^}]*background:\s*var\(--records-query-bg\)[^}]*color:\s*white/s)
    expect(mainStyles).toMatch(/\.filter-btn:disabled\s*\{[^}]*background:\s*var\(--bg-secondary\)[^}]*color:\s*var\(--text-sub\)/s)
    expect(mainStyles).not.toMatch(/\.filter-btn:disabled\s*\{[^}]*opacity:/s)
  })

  it('uses symmetric desktop scrollbars and vertically fills record states', () => {
    expect(mainStyles).toMatch(/\.records-modal-content\s*\{[^}]*scrollbar-gutter:\s*auto/s)
    expect(mainStyles).toMatch(/@media \(min-width: (?:560|768)px\)[\s\S]*\.records-modal-content\s*\{[^}]*scrollbar-gutter:\s*stable both-edges/s)
    expect(mainStyles).toMatch(/\.records-state\s*\{[^}]*min-height:\s*100%[^}]*height:\s*100%/s)
    expect(mainStyles).not.toMatch(/\.records-state\s*\{[^}]*min-height:\s*240px/s)
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

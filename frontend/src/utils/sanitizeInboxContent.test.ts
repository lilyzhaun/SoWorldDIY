import { describe, expect, it, vi } from 'vitest'

vi.mock('dompurify', () => {
  return {
    default: {
      sanitize: (html: string) => String(html).replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, ''),
    },
    sanitize: (html: string) => String(html).replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, ''),
  }
})

import { sanitizeInboxContent } from './sanitizeInboxContent'

describe('sanitizeInboxContent', () => {
  it('sanitizes markup in node environment without document wrapping', () => {
    const out = sanitizeInboxContent('<b>ok</b><script>alert(1)</script>')
    expect(out).toContain('ok')
    expect(out.toLowerCase()).not.toContain('<script')
  })

  it('preserves plain content', () => {
    expect(sanitizeInboxContent('plain')).toContain('plain')
  })
})

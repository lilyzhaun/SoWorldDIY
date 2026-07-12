import DOMPurify from 'dompurify'

import { splitInboxTimeTokens } from './inboxTimeTokens'

export function sanitizeInboxContent(html: string): string {
  const sanitizedHtml = DOMPurify.sanitize(html)
  if (typeof document === 'undefined') return sanitizedHtml
  const template = document.createElement('template')
  template.innerHTML = sanitizedHtml
  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT)
  const textNodes: Text[] = []
  while (walker.nextNode()) {
    if (walker.currentNode instanceof Text) textNodes.push(walker.currentNode)
  }
  for (const textNode of textNodes) {
    const parts = splitInboxTimeTokens(textNode.data)
    if (!parts.some((part) => part.nowrap)) continue
    const fragment = document.createDocumentFragment()
    for (const part of parts) {
      if (!part.nowrap) fragment.append(part.text)
      else {
        const span = document.createElement('span')
        span.className = 'inbox-nowrap-token'
        span.textContent = part.text
        fragment.append(span)
      }
    }
    textNode.replaceWith(fragment)
  }
  return template.innerHTML
}

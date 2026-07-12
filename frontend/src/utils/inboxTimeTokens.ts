export type InboxTimeTokenPart = {
  readonly text: string
  readonly nowrap: boolean
}

const INBOX_TIME_TOKEN_PATTERN = /\d+(?:小時|分鐘|個月|天|日|秒|年)/gu

export function splitInboxTimeTokens(text: string): InboxTimeTokenPart[] {
  const parts: InboxTimeTokenPart[] = []
  let cursor = 0
  for (const match of text.matchAll(INBOX_TIME_TOKEN_PATTERN)) {
    if (match.index > cursor) parts.push({ text: text.slice(cursor, match.index), nowrap: false })
    parts.push({ text: match[0], nowrap: true })
    cursor = match.index + match[0].length
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor), nowrap: false })
  return parts
}

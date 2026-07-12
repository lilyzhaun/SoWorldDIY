const MAX_CAPTURE_GROUPS = 4
const MAX_ATOMS_PER_BRANCH = 8

export type BranchValidation =
  | { readonly valid: true }
  | { readonly valid: false; readonly message: string }

export function parseBackreference(source: string, index: number): number | null {
  if (source[index] !== '\\') return null
  const digit = source[index + 1]
  if (digit === undefined || digit < '1' || digit > '4') return null

  const next = source[index + 2]
  if (next !== undefined && next >= '0' && next <= '9') return null

  return index + 2
}

function validateCaptureGroupQuantifier(source: string, start: number): number | null {
  const character = source[start]
  if (character !== '{') return start

  const end = source.indexOf('}', start + 1)
  if (end < 0) return null
  const body = source.slice(start + 1, end)
  const match = /^(\d+)$/.exec(body)
  if (!match) return null

  const text = match[1]
  if (!text) return null
  const value = Number.parseInt(text, 10)
  if (value < 1 || value > 8) return null

  return end + 1
}

function validateCaptureBody(source: string, start: number, end: number): BranchValidation {
  if (end <= start) return { valid: false, message: '捕获组不能为空' }

  let index = start
  let atoms = 0

  while (index < end) {
    const character = source[index]
    let nextIndex: number | null

    if (character === '(') return { valid: false, message: '捕获组内不允许出现嵌套分组' }
    if (character === '\\') {
      if (source[index + 1] !== 'd') return { valid: false, message: '捕获组内只支持数字相关原子' }
      nextIndex = index + 2
    } else if (character === '[') {
      nextIndex = validateClass(source, index)
      if (nextIndex === null) return { valid: false, message: '数字字符类或范围格式无效' }
    } else if (character === '.') {
      nextIndex = index + 1
    } else if (character >= '0' && character <= '9') {
      nextIndex = index + 1
    } else {
      return { valid: false, message: '捕获组内只支持数字字符、通配符、数字类和数字范围' }
    }

    const quantifiedIndex = validateCaptureGroupQuantifier(source, nextIndex)
    if (quantifiedIndex === null) return { valid: false, message: '捕获组内量词只允许使用{n}(1到8)' }
    if (isQuantifierStart(source[quantifiedIndex])) return { valid: false, message: '捕获组内不允许连续或嵌套量词' }
    atoms += 1
    if (atoms > MAX_ATOMS_PER_BRANCH) return { valid: false, message: '每个分支最多允许 8 个匹配项' }
    index = quantifiedIndex
  }

  return { valid: true }
}

export function validateCapture(
  source: string,
  start: number,
  openGroups: number,
  atoms: number,
): {
  readonly nextIndex: number
  readonly openGroups: number
  readonly atoms: number
} | null {
  const index = start + 1
  if (openGroups >= MAX_CAPTURE_GROUPS) return null
  if (source[index] === '?') return null
  if (index >= source.length) return null

  const closeIndex = source.indexOf(')', index)
  if (closeIndex < 0) return null

  const bodyValidation = validateCaptureBody(source, index, closeIndex)
  if (!bodyValidation.valid) return null

  if (isQuantifierStart(source[closeIndex + 1])) return null

  return {
    nextIndex: closeIndex + 1,
    openGroups: openGroups + 1,
    atoms: atoms + 1,
  }
}

function isQuantifierStart(character: string | undefined): boolean {
  return character === '?' || character === '*' || character === '+' || character === '{'
}

function validateClass(source: string, start: number): number | null {
  const end = source.indexOf(']', start + 1)
  if (end < 0 || end === start + 1) return null

  let index = start + 1
  while (index < end) {
    const rangeStart = source[index]
    if (!rangeStart || rangeStart < '0' || rangeStart > '9') return null
    index += 1
    if (source[index] !== '-') continue

    const rangeEnd = source[index + 1]
    if (!rangeEnd || rangeEnd < rangeStart || rangeEnd > '9') return null
    index += 2
  }

  return end + 1
}

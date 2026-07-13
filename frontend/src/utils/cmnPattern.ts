import type { BranchValidation } from './cmnPatternCapture'
import { parseBackreference, validateCapture } from './cmnPatternCapture'

const MAX_PATTERN_LENGTH = 32
const MAX_BRANCHES = 4
const MAX_ATOMS_PER_BRANCH = 8
const ASCII_DIGITS = /^\d{8}$/

export type CmnPattern =
  | { readonly kind: 'empty' }
  | { readonly kind: 'literal'; readonly value: string }
  | { readonly kind: 'regex'; readonly source: string }
  | { readonly kind: 'invalid'; readonly message: string }

export type CmnMatchRange = {
  readonly start: number
  readonly end: number
}

export type CmnCandidateSegment = {
  readonly text: string
  readonly highlighted: boolean
}

function invalid(message: string): CmnPattern {
  return { kind: 'invalid', message }
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

function validateQuantifier(source: string, start: number): number | null {
  const character = source[start]
  if (character === '?' || character === '*' || character === '+') return start + 1
  if (character !== '{') return start

  const end = source.indexOf('}', start + 1)
  if (end < 0) return null
  const body = source.slice(start + 1, end)
  const match = /^(\d+)(?:,(\d+))?$/.exec(body)
  if (!match) return null

  const minimumText = match[1]
  if (!minimumText) return null
  const minimum = Number.parseInt(minimumText, 10)
  const maximumText = match[2]
  const maximum = maximumText === undefined ? minimum : Number.parseInt(maximumText, 10)
  if (minimum > 8 || maximum > 8 || minimum > maximum) return null

  return end + 1
}

function validateBranch(source: string, hasTopLevelAlternation = false): BranchValidation {
  let index = 0
  let atoms = 0
  let openGroups = 0

  while (index < source.length) {
    const character = source[index]
    if (character === '^') {
      if (index !== 0) return { valid: false, message: '起始锚点只能放在分支开头' }
      index += 1
      continue
    }
    if (character === '$') {
      if (index !== source.length - 1) return { valid: false, message: '结束锚点只能放在分支末尾' }
      index += 1
      continue
    }
    if (isQuantifierStart(character) || character === '}') {
      return { valid: false, message: '量词前必须有数字匹配项' }
    }

    let nextIndex: number | null
    if (character === '(') {
      if (hasTopLevelAlternation) return { valid: false, message: '分支中存在捕获组时不支持顶层替换分支' }
      const capture = validateCapture(source, index, openGroups, atoms)
      if (capture === null) return { valid: false, message: '捕获组语法不安全' }
      index = capture.nextIndex
      openGroups = capture.openGroups
      atoms = capture.atoms
      if (atoms > MAX_ATOMS_PER_BRANCH) return { valid: false, message: '每个分支最多允许 8 个匹配项' }
      continue
    }

    if (character === '\\') {
      const backreference = parseBackreference(source, index)
      if (backreference !== null) {
        if (hasTopLevelAlternation) return { valid: false, message: '反向引用与顶层替换分支不兼容' }
        const groupId = Number.parseInt(source[index + 1], 10)
        if (groupId === 0 || groupId > openGroups) return { valid: false, message: '反向引用必须引用已闭合的捕获组' }
        nextIndex = backreference
      } else if (source[index + 1] === 'd') {
        nextIndex = index + 2
      } else {
        return { valid: false, message: '包含不支持的正则语法' }
      }
    } else if (character && character >= '0' && character <= '9') {
      nextIndex = index + 1
    } else if (character === '.') {
      nextIndex = index + 1
    } else if (character === '[') {
      nextIndex = validateClass(source, index)
    } else {
      return { valid: false, message: '包含不支持的正则语法' }
    }

    if (nextIndex === null) return { valid: false, message: '数字字符类或范围格式无效' }
    atoms += 1
    if (atoms > MAX_ATOMS_PER_BRANCH) return { valid: false, message: '每个分支最多允许 8 个匹配项' }

    const quantifiedIndex = validateQuantifier(source, nextIndex)
    if (quantifiedIndex === null) return { valid: false, message: '量词格式或范围无效' }
    if (quantifiedIndex !== nextIndex && isQuantifierStart(source[quantifiedIndex])) {
      return { valid: false, message: '不允许连续或嵌套量词' }
    }
    index = quantifiedIndex
  }

  return atoms > 0 ? { valid: true } : { valid: false, message: '每个分支至少需要一个数字匹配项' }
}

export function parseCmnPattern(input: string): CmnPattern {
  if (input.length === 0) return { kind: 'empty' }
  if (input.length > MAX_PATTERN_LENGTH) return invalid('模式最多 32 个 ASCII 字符')
  for (let index = 0; index < input.length; index += 1) {
    if (input.charCodeAt(index) > 0x7f) return invalid('模式只允许 ASCII 字符')
  }
  if (/^\d+$/.test(input)) return { kind: 'literal', value: input }

  const branches = input.split('|')
  if (branches.length > MAX_BRANCHES) return invalid('最多允许 4 个非空分支')
  if (branches.some((branch) => branch.length === 0)) return invalid('分支不能为空')

  const hasTopLevelAlternation = branches.length > 1

  const containsBackreference = /\\[1-4]/.test(input)
  const containsCapture = input.includes('(')

  for (const branch of branches) {
    const result = validateBranch(branch, hasTopLevelAlternation && (containsBackreference || containsCapture))
    if (!result.valid) return invalid(result.message)
  }

  try {
    const expression = new RegExp(input)
    if (expression.test('')) return invalid('模式不能匹配空字符串')
  } catch (error) {
    if (error instanceof SyntaxError) return invalid('正则模式格式无效')
    throw error
  }

  return { kind: 'regex', source: input }
}

function literalRanges(candidate: string, value: string): readonly CmnMatchRange[] {
  if (value.length === 0) return []

  const ranges: CmnMatchRange[] = []
  let start = candidate.indexOf(value)
  while (start >= 0) {
    ranges.push({ start, end: start + value.length })
    start = candidate.indexOf(value, start + value.length)
  }
  return ranges
}

export function findCmnPatternRanges(candidate: string, input: string): readonly CmnMatchRange[] {
  if (!ASCII_DIGITS.test(candidate)) return []
  const pattern = parseCmnPattern(input)

  switch (pattern.kind) {
    case 'empty':
    case 'invalid':
      return []
    case 'literal':
      return literalRanges(candidate, pattern.value)
    case 'regex': {
      const ranges: CmnMatchRange[] = []
      const expression = new RegExp(pattern.source, 'g')
      for (const match of candidate.matchAll(expression)) {
        if (match.index !== undefined && match[0].length > 0) {
          ranges.push({ start: match.index, end: match.index + match[0].length })
        }
      }
      return ranges
    }
    default:
      return pattern satisfies never
  }
}

export function segmentCmnCandidate(
  candidate: string,
  ranges: readonly CmnMatchRange[],
): readonly CmnCandidateSegment[] {
  if (ranges.length === 0) return [{ text: candidate, highlighted: false }]

  const segments: CmnCandidateSegment[] = []
  let cursor = 0
  for (const range of ranges) {
    if (range.start > cursor) segments.push({ text: candidate.slice(cursor, range.start), highlighted: false })
    segments.push({ text: candidate.slice(range.start, range.end), highlighted: true })
    cursor = range.end
  }
  if (cursor < candidate.length) segments.push({ text: candidate.slice(cursor), highlighted: false })
  return segments
}

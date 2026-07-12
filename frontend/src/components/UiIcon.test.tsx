import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { UiIcon, type UiIconName } from './UiIcon'

const iconNames = [
  'alert-triangle',
  'arrow-left',
  'calendar',
  'check',
  'check-circle',
  'chevron-down',
  'chevron-right',
  'circle',
  'close',
  'info-circle',
  'minus',
  'phone',
  'plus',
  'refresh',
  'search',
  'trash',
  'user',
  'x-circle',
] as const satisfies readonly UiIconName[]

describe('UiIcon', () => {
  it.each(iconNames)('renders one consistent currentColor SVG for %s', (name) => {
    const html = renderToStaticMarkup(<UiIcon name={name} />)

    expect(html.match(/<svg/g)).toHaveLength(1)
    expect(html).toContain('viewBox="0 0 20 20"')
    expect(html).toContain(`data-ui-icon="${name}"`)
    expect(html).toContain('width="20"')
    expect(html).toContain('height="20"')
    expect(html).toContain('fill="none"')
    expect(html).toContain('stroke="currentColor"')
    expect(html).toContain('stroke-width="1.9"')
    expect(html).toContain('stroke-linecap="round"')
    expect(html).toContain('stroke-linejoin="round"')
    expect(html).toContain('aria-hidden="true"')
    expect(html).toContain('focusable="false"')
  })

  it('applies the requested class and supported size', () => {
    const html = renderToStaticMarkup(<UiIcon name="search" size={16} className="search-icon" />)

    expect(html).toContain('class="search-icon"')
    expect(html).toContain('width="16"')
    expect(html).toContain('height="16"')
  })
})

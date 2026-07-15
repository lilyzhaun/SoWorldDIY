import type { Category, Plan } from '@/types'

export function filterPlansForCategory(
  plans: Plan[],
  search: string,
  category: Category,
  showFreePlans: boolean,
): Plan[] {
  const keyword = search.toLowerCase().trim()
  return plans.filter((plan) => {
    if (category === 'CMN' || category === 'SUBSCRIBED') return false
    if (plan.price <= 0 && !showFreePlans) return false
    if (category === 'OTHER' && plan.category !== 'VOICE' && plan.category !== 'OTHER') return false
    if (category !== 'ALL' && category !== 'OTHER' && plan.category !== category) return false
    if (!keyword) return true
    return `${plan.name}${plan.desc}${plan.price}`.toLowerCase().includes(keyword)
  })
}

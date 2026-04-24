import { useEffect } from 'react'

export function useBodyScrollLock(lock: boolean): void {
  useEffect(() => {
    const isDesktop = window.matchMedia('(min-width: 768px) and (orientation: landscape)').matches
    if (!isDesktop) {
      document.body.classList.toggle('no-scroll', lock)
    } else {
      document.body.classList.remove('no-scroll')
    }
    return () => document.body.classList.remove('no-scroll')
  }, [lock])
}

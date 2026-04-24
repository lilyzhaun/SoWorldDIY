import { useEffect } from 'react'

export function useServiceWorker(buildVersion: string): void {
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      window.addEventListener(
        'load',
        () => {
          navigator.serviceWorker.register(`/sw.js?v=${encodeURIComponent(buildVersion)}`).catch(() => {})
        },
        { once: true },
      )
    }
  }, [buildVersion])
}

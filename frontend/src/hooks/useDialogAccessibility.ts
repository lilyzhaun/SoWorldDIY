import { useEffect, useRef } from 'react'

const FOCUSABLE_SELECTOR =
  'a[href], area[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), iframe, object, embed, [contenteditable="true"], [tabindex]:not([tabindex="-1"])'

export function getNextDialogFocusIndex(currentIndex: number, focusableCount: number, backwards: boolean): number {
  if (focusableCount === 0) return -1
  if (currentIndex < 0) return backwards ? focusableCount - 1 : 0
  return (currentIndex + (backwards ? -1 : 1) + focusableCount) % focusableCount
}

function getVisibleFocusableElements(dialog: HTMLElement): HTMLElement[] {
  return Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => {
    if (element.closest('[hidden], [inert], [aria-hidden="true"]')) return false
    const style = window.getComputedStyle(element)
    return style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0
  })
}

export function useDialogAccessibility(open: boolean, onClose: () => void): React.RefObject<HTMLDivElement> {
  const dialogRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = dialogRef.current
    if (!dialog) return
    const initialFocus =
      dialog.querySelector<HTMLElement>('[data-dialog-initial-focus]') ?? getVisibleFocusableElements(dialog)[0]
    initialFocus?.focus()

    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const focusableElements = getVisibleFocusableElements(dialog)
      const currentIndex = focusableElements.indexOf(
        document.activeElement instanceof HTMLElement ? document.activeElement : dialog,
      )
      const nextIndex = getNextDialogFocusIndex(currentIndex, focusableElements.length, event.shiftKey)
      event.preventDefault()
      if (nextIndex < 0) dialog.focus()
      else focusableElements[nextIndex]?.focus()
    }
    const handleFocusIn = (event: FocusEvent): void => {
      if (event.target instanceof Node && dialog.contains(event.target)) return
      const focusableElements = getVisibleFocusableElements(dialog)
      ;(focusableElements[0] ?? dialog).focus()
    }
    dialog.tabIndex = -1
    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('focusin', handleFocusIn)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('focusin', handleFocusIn)
      previouslyFocused?.focus()
    }
  }, [open])

  return dialogRef
}

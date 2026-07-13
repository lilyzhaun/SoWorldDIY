import { useState } from 'react'

import type { StatusTone } from '@/components/StatusMessage'
import type { ModalMode } from '@/types'

export type ModalKind = 'alert' | 'switch' | 'cart' | 'purchase' | 'transfer' | null

export type AlertState = {
  readonly text: string
  readonly tone?: StatusTone
}

type UseAppModalOptions = {
  readonly onAfterClose?: () => void
}

type AppModalState = {
  readonly showModal: boolean
  readonly modalTitle: string
  readonly modalMode: ModalMode
  readonly modalKind: ModalKind
  readonly alert: AlertState
  readonly showAlert: (text: string, title?: string, tone?: StatusTone) => void
  readonly closeCustomModal: () => void
  readonly openSwitchModal: () => void
  readonly openCartModal: (itemCount: number) => void
  readonly openKind: (kind: Exclude<ModalKind, null | 'alert'>, title: string, mode?: ModalMode) => void
}

export function useAppModal(options: UseAppModalOptions = {}): AppModalState {
  const [showModal, setShowModal] = useState(false)
  const [modalTitle, setModalTitle] = useState('标题')
  const [modalMode, setModalMode] = useState<ModalMode>('center')
  const [modalKind, setModalKind] = useState<ModalKind>(null)
  const [alert, setAlert] = useState<AlertState>({ text: '' })

  const showAlert = (text: string, title = '提示', tone?: StatusTone): void => {
    setModalKind('alert')
    setModalTitle(title)
    setModalMode('center')
    setAlert(tone ? { text, tone } : { text })
    setShowModal(true)
  }

  const closeCustomModal = (): void => {
    setShowModal(false)
    options.onAfterClose?.()
  }

  const openKind = (kind: Exclude<ModalKind, null | 'alert'>, title: string, mode: ModalMode = 'center'): void => {
    setModalKind(kind)
    setModalTitle(title)
    setModalMode(mode)
    setShowModal(true)
  }

  const openSwitchModal = (): void => {
    openKind('switch', '账号管理', 'bottom-sheet')
  }

  const openCartModal = (itemCount: number): void => {
    if (itemCount === 0) return
    openKind('cart', '购物车', 'center')
  }

  return {
    showModal,
    modalTitle,
    modalMode,
    modalKind,
    alert,
    showAlert,
    closeCustomModal,
    openSwitchModal,
    openCartModal,
    openKind,
  }
}

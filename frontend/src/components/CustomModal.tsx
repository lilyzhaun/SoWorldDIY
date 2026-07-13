import type { ModalMode } from '@/types'
import { useDialogAccessibility } from '@/hooks/useDialogAccessibility'

type CustomModalProps = { readonly actions: React.ReactNode; readonly children: React.ReactNode; readonly mode: ModalMode; readonly onClose: () => void; readonly open: boolean; readonly title: string }

export function CustomModal({ actions, children, mode, onClose, open, title }: CustomModalProps): JSX.Element {
  const dialogRef = useDialogAccessibility(open, onClose)
  return <div ref={dialogRef} id="customModal" className={`modal-overlay ${open ? 'show' : ''} ${mode === 'bottom-sheet' ? 'bottom-sheet-overlay' : ''}`} role="dialog" aria-modal="true" aria-labelledby="customModalTitle" onClick={(event) => { if (event.target === event.currentTarget) onClose() }}><div className="modal-box"><div className="modal-title" id="customModalTitle">{title}</div><div className="modal-text" id="modalText">{mode === 'bottom-sheet' ? <div className="modal-handle"></div> : null}{children}</div><div className="modal-actions" id="modalActions">{actions}</div></div></div>
}

import type { ModalMode } from '../types'

type CustomModalProps = { readonly actions: React.ReactNode; readonly children: React.ReactNode; readonly mode: ModalMode; readonly onClose: () => void; readonly open: boolean; readonly title: string }

export function CustomModal({ actions, children, mode, onClose, open, title }: CustomModalProps): JSX.Element {
  return <div id="customModal" className={`modal-overlay ${open ? 'show' : ''} ${mode === 'bottom-sheet' ? 'bottom-sheet-overlay' : ''}`} onClick={(event) => { if (event.target === event.currentTarget) onClose() }}><div className="modal-box"><div className="modal-title" id="modalTitle">{title}</div><div className="modal-text" id="modalText">{mode === 'bottom-sheet' ? <div className="modal-handle"></div> : null}{children}</div><div className="modal-actions" id="modalActions">{actions}</div></div></div>
}

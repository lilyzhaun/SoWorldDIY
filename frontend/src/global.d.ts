declare global {
  interface Window {
    switchTab?: (type: 'password' | 'otp') => void
    handleSendOtp?: () => Promise<void>
    openOfficialTopUp?: () => void
    openHistory?: (event: MouseEvent | React.MouseEvent<HTMLElement>) => void
    openInbox?: (event: MouseEvent | React.MouseEvent<HTMLElement>) => void
    handleLogout?: () => void
    filterPlans?: () => void
    switchCategory?: (category: string, element?: HTMLElement) => void
    refreshProfileData?: () => void
    openCartView?: () => void
    refreshInbox?: () => void
    closeInbox?: () => void
    closeHistory?: () => void
    fetchHistory?: (manual?: boolean, silent?: boolean) => void
    viewMessage?: (index: number) => void
    viewHistoryDetail?: (index: number) => void
    openCartView?: () => void
    updateCartItem?: (index: number, delta: number) => void
    removeCartItem?: (index: number) => void
  }
}

declare module '*.css'

export {}

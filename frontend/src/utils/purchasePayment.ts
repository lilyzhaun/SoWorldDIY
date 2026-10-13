export function purchasePayment(draft: { price: number; txnAmount: number; newLine: boolean }, balance: string) {
  const currentBalance = Math.max(0, Number.parseFloat(balance) || 0)
  const maxAllowed = draft.newLine ? 0 : Math.min(currentBalance, draft.price)
  const validTxn = Math.max(0, Math.min(draft.txnAmount, maxAllowed))
  return { currentBalance, maxAllowed, validTxn, payAmount: Math.max(0, draft.price - validTxn) }
}

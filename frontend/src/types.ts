export type UsageItem = {
  name?: string
  unit?: string
  total?: number
  remain?: number
  percent?: number
  canTransfer?: boolean
  minTransfer?: number
  balanceResourceId?: string | number
  productFamily?: string
}

export type ActiveOffer = {
  offerId: string
  name: string
  desc?: string
  price?: number
  endDate?: string
  isVoWifi?: boolean
  planStatus?: string
  usage?: UsageItem[]
  offerSubType?: string
}

export type Subscription = {
  mobile?: string
  activationDate?: string
  subsEndDate?: string
  subscriptionId: string
  brand?: string
  iccid?: string
  status?: string
  activeOffers?: ActiveOffer[]
}

export type AvailableAccount = {
  identifier: string
  active: boolean
  subBrand: string
}

export type ProfileResponse = {
  status: string
  data: {
    subscriptions: Subscription[]
    current?: Subscription
    available_accounts?: AvailableAccount[]
  }
}

export type Plan = {
  offerId: string
  name: string
  price: number
  validity: string
  desc: string
  isVoWifi?: boolean
  category: string
}

export type InboxMessage = {
  subject: string
  content: string
  post_dt: string
  intended_subscription_id: string
}

export type HistoryItem = {
  transactionDate?: string
  type?: string
  purchase?: {
    purchaseStatus?: string
    purchaseType?: string
    purchaseId?: string
    paymentDetail?: {
      amnt?: number
      walletAmt?: number
    }
    purchaseSubscriptions?: Array<{
      offers?: Array<{
        offerNameChi?: string
        offerName?: string
        offerDescChi?: string
        offerDesc?: string
      }>
    }>
    offer?: Array<{
      offerNameChi?: string
      offerName?: string
      offerDescChi?: string
      offerDesc?: string
    }>
  }
}

export type CartItem = {
  offerId: string
  name: string
  price: number
  quantity: number
}

export type CmnCheckResponse = {
  status: string
  message?: string
  data?: {
    offerId: string
    offerSubType?: string
    price: number
  }
}

export type TransferDraft = {
  userOfferId: string
  balanceResourceId: string
  unit: string
  minTransfer: number
  productFamily: string
  maxValue: number
}

export type ModalMode = 'center' | 'bottom-sheet'

export type Category = 'ALL' | 'LOCAL' | 'TRAVEL' | 'SUBSCRIBED' | 'OTHER' | 'CMN'

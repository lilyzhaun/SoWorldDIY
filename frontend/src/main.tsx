import React from 'react'
import ReactDOM from 'react-dom/client'

import '@/styles/main.css'
import { MainPage } from '@/MainPage'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MainPage />
  </React.StrictMode>,
)

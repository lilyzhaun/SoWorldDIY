import React from 'react'
import ReactDOM from 'react-dom/client'

import './styles/login.css'
import { LoginPage } from './LoginPage'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LoginPage />
  </React.StrictMode>,
)

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App'
import { LDMProvider } from './context/LDMContext'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <LDMProvider>
      <App />
    </LDMProvider>
  </StrictMode>,
)

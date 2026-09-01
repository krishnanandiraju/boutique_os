import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './features/demo/integration-polish.css'
import './features/demo/fit-memory-polish.css'
import ClientDemoWorkspace from './features/demo/ClientDemoWorkspace'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ClientDemoWorkspace />
  </StrictMode>,
)

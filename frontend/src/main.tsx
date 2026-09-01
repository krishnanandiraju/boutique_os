import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MantineProvider } from '@mantine/core'
import '@mantine/core/styles.css'
import './index.css'
import './features/demo/integration-polish.css'
import './features/demo/fit-memory-polish.css'
import './features/demo/modern-mantine.css'
import ClientDemoWorkspace from './features/demo/ClientDemoWorkspace'
import { boutiqueTheme } from './app/theme'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={boutiqueTheme} defaultColorScheme="light">
      <ClientDemoWorkspace />
    </MantineProvider>
  </StrictMode>,
)

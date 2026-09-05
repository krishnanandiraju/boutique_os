import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MantineProvider } from '@mantine/core'
import '@mantine/core/styles.css'
import './index.css'
import BoutiqueWorkspace from './features/workspace/BoutiqueWorkspace'
import { boutiqueTheme } from './app/theme'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={boutiqueTheme} defaultColorScheme="light">
      <BoutiqueWorkspace />
    </MantineProvider>
  </StrictMode>,
)

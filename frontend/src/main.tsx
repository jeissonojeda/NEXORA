import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import ErrorBoundary from './components/ui/ErrorBoundary.tsx'
import { AuthProvider } from './contexts/AuthContext.tsx'
import { LicenseProvider } from './contexts/LicenseContext.tsx'
import { SettingsProvider } from './contexts/SettingsContext.tsx'
import { ThemeProvider } from './contexts/ThemeContext.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary
      context="root"
      title="Se produjo un error inesperado."
      description="La aplicación encontró un problema al renderizar esta pantalla. Puedes recargar para continuar. Si el problema persiste, revisa la consola del navegador."
      retryLabel="Recargar"
      onRetry={() => window.location.reload()}
    >
      <BrowserRouter>
        <ThemeProvider>
          <LicenseProvider>
            <AuthProvider>
              <SettingsProvider>
                <App />
              </SettingsProvider>
            </AuthProvider>
          </LicenseProvider>
        </ThemeProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)

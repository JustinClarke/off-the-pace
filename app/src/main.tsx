// App entrypoint mounts React root with QueryClient, ThemeProvider, and the browser router.
import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from './state/ThemeContext'
import { router } from './App'
import { initObservability } from './observability'
import { reportWebVitals } from './observability/webVitals'
import './styles.css'

// Start error tracking before render (no-op unless VITE_SENTRY_DSN is set). Fire-and-forget so
// the dynamic Sentry import never delays first paint.
void initObservability()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
)

// Report Core Web Vitals once the app has mounted (no-op unless RUM is enabled).
void reportWebVitals()

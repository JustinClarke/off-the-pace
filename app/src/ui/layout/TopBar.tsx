// Top navigation bar theme toggle, GitHub link, and EngineStatus indicator.
import { useTheme } from '../../state/ThemeContext'
import EngineStatus from './EngineStatus'

export default function TopBar() {
  const { resolvedTheme, setTheme } = useTheme()

  return (
    <header className="flex items-center justify-between px-4 border-b border-border bg-surface" style={{ height: 56 }}>
      <EngineStatus />
      <div className="flex items-center gap-2 ml-auto">
        <button
          onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
          className="p-2 rounded-md text-muted hover:bg-surface hover:text-[rgb(var(--color-text))] transition-colors text-sm"
          aria-label="Toggle theme"
        >
          {resolvedTheme === 'dark' ? '☀' : '☾'}
        </button>
      </div>
    </header>
  )
}

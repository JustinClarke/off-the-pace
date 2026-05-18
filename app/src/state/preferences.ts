// Typed localStorage wrapper namespaced under 'otp:'; used by ThemeContext and CSV export settings.
const PREFIX = 'otp:'

function get<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(PREFIX + key)
    return raw !== null ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function set<T>(key: string, value: T): void {
  localStorage.setItem(PREFIX + key, JSON.stringify(value))
}

export const preferences = {
  get csvDelimiter(): string { return get('csv-delimiter', ',') },
  set csvDelimiter(v: string) { set('csv-delimiter', v) },

  get hideIntroModal(): boolean { return get('hide-intro', false) },
  set hideIntroModal(v: boolean) { set('hide-intro', v) },

  get sidebarCollapsed(): boolean { return get('sidebar-collapsed', false) },
  set sidebarCollapsed(v: boolean) { set('sidebar-collapsed', v) },
}

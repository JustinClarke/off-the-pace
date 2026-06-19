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

  // Query Lab history: most-recent-first, de-duplicated, capped.
  get queryHistory(): string[] { return get<string[]>('query-history', []) },
  set queryHistory(v: string[]) { set('query-history', v) },
}

const QUERY_HISTORY_CAP = 20

/** Push a query to the front of the history (de-duped, capped). No-op for blanks. */
export function pushQueryHistory(sql: string): void {
  const trimmed = sql.trim()
  if (!trimmed) return
  const next = [trimmed, ...preferences.queryHistory.filter(q => q !== trimmed)].slice(0, QUERY_HISTORY_CAP)
  preferences.queryHistory = next
}

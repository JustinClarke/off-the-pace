// URL search-param helpers used by filter state and deep-link generation.
export function getSearchParam(key: string): string | null {
  return new URLSearchParams(window.location.search).get(key)
}

export function setSearchParam(key: string, value: string): string {
  const params = new URLSearchParams(window.location.search)
  params.set(key, value)
  return `${window.location.pathname}?${params.toString()}`
}

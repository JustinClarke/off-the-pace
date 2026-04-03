// Name formatters: driver code normalisation, constructor display names, circuit short names.
export function formatDriverCode(code: string): string {
  return code.toUpperCase()
}

export function formatDriverFull(firstName: string, lastName: string): string {
  return `${firstName} ${lastName}`
}

export function formatConstructorName(name: string): string {
  return name
}

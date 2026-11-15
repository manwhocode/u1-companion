export function u1t (text: string, values: Record<string, unknown> = {}) { return text.replace(/\{(\w+)\}/g, (m, key: string) => key in values ? String(values[key]) : m) }

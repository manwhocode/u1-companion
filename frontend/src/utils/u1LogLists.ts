export function visibleLogRows<T extends { id: string }> (rows: T[], archived: string[] = [], includeArchived = false): T[] {
  if (includeArchived) return rows
  const hidden = new Set(archived)
  return rows.filter(row => !hidden.has(row.id))
}

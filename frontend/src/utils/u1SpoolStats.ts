import { u1t } from '@/plugins/i18n'
export interface UsageRow { head: number; name: string; grams: number; spoolId?: string; colorId?: string; colorName?: string; pricePerGram?: number }
export interface UsageRecord { id: string; filename: string; status: string; time: number; rows: UsageRow[]; state: 'review' | 'applied'; method: string }
export type UsagePeriod = 'job' | 'day' | 'month' | 'year'

const euros = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'EUR' })
const unitEuros = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'EUR', maximumFractionDigits: 6 })

export function formatCost (value: number) { return euros.format(value) }
export function formatUnitPrice (value: number) { return unitEuros.format(value) }

export function usageRows (records: UsageRecord[], period: UsagePeriod) {
  const groups = new Map<string, { key: string; time: number; name: string; jobs: number; grams: number; cost: number; pricedGrams: number }>()
  for (const record of records) {
    if (record.state !== 'applied') continue
    const date = new Date(record.time * 1000)
    const year = date.getFullYear()
    const month = date.getMonth()
    const day = date.getDate()
    const start = period === 'job' ? date : new Date(year, period === 'year' ? 0 : month, period === 'day' ? day : 1)
    const time = start.getTime()
    const key = period === 'job' ? record.id : String(time)
    let group = groups.get(key)
    if (!group) {
      const name = period === 'job' ? record.filename : ''
      group = { key, time, name, jobs: 0, grams: 0, cost: 0, pricedGrams: 0 }
      groups.set(key, group)
    }
    group.jobs++
    for (const row of record.rows) {
      group.grams += row.grams
      if (typeof row.pricePerGram === 'number' && Number.isFinite(row.pricePerGram) && row.pricePerGram >= 0) {
        group.cost += row.grams * row.pricePerGram
        group.pricedGrams += row.grams
      }
    }
  }
  return [...groups.values()]
}

export type UsageDimension = 'time' | 'spool' | 'color'

// Local calendar days, including the entire end day (also across DST changes).
export function filterUsage (records: UsageRecord[], from = '', to = '') {
  const boundary = (value: string, next: boolean) => {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day + (next ? 1 : 0)).getTime() / 1000
  }
  const start = from ? boundary(from, false) : -Infinity
  const end = to ? boundary(to, true) : Infinity
  return records.filter(record => record.time >= start && record.time < end)
}

export function cumulativeRows (records: UsageRecord[], dimension: 'spool' | 'color', totals: Record<string, number> = {}) {
  const groups = new Map<string, { key: string; name: string; jobs: number; grams: number; cost: number; pricedGrams: number; undatedGrams: number; jobIds: Set<string> }>()
  const recorded = new Map<string, number>()
  const names = new Map<string, string>()
  const get = (key: string, name: string) => {
    let group = groups.get(key)
    if (!group) {
      group = { key, name, jobs: 0, grams: 0, cost: 0, pricedGrams: 0, undatedGrams: 0, jobIds: new Set() }
      groups.set(key, group)
    }
    return group
  }
  const seen = new Set<string>()
  for (const record of records) {
    if (record.state !== 'applied' || seen.has(record.id)) continue
    seen.add(record.id)
    for (const row of record.rows) {
      const spool = row.spoolId || 'unknown'
      const key = dimension === 'spool' ? spool : row.colorId || 'unknown'
      const name = dimension === 'spool' ? row.name || u1t("Катушка ") + spool : row.colorId ? row.colorName || u1t("Цвет ") + row.colorId : u1t("Цвет не сохранён в истории")
      const group = get(key, name)
      group.jobIds.add(record.id)
      group.jobs = group.jobIds.size
      group.grams += row.grams
      if (typeof row.pricePerGram === 'number' && Number.isFinite(row.pricePerGram) && row.pricePerGram >= 0) {
        group.cost += row.grams * row.pricePerGram
        group.pricedGrams += row.grams
      }
      recorded.set(spool, (recorded.get(spool) || 0) + row.grams)
      if (row.name) names.set(spool, row.name)
    }
  }
  // Legacy totals have no date, price or reliable color identity. Never assign
  // them to today's base color, and never include them in a selected date range.
  for (const [spool, total] of Object.entries(totals)) {
    const extra = Math.max(0, total - (recorded.get(spool) || 0))
    if (!extra) continue
    const group = dimension === 'spool'
      ? get(spool, names.get(spool) || u1t("Катушка ") + spool)
      : get('unknown', u1t("Цвет не сохранён в истории"))
    group.grams += extra
    group.undatedGrams += extra
  }
  return [...groups.values()].map(({ jobIds, ...group }) => group)
}

interface ErrorRateEvent { id: string; jobId: string; spools: { spoolId: string; colorId?: string }[] }

// Compare the same finished jobs, not unrelated event-day and consumption-day
// totals. A message belongs only to the spool/color snapshot linked to that job.
export function errorRateRows (records: UsageRecord[], events: ErrorRateEvent[], dimension: 'spool' | 'color', from = '', to = '', spoolId?: string | null, colorId?: string | null) {
  const eventsByJob = new Map<string, ErrorRateEvent[]>()
  const seenEvents = new Set<string>()
  for (const event of events) {
    if (seenEvents.has(event.id)) continue
    seenEvents.add(event.id)
    const key = event.jobId.toUpperCase()
    const values = eventsByJob.get(key) || []
    values.push(event)
    eventsByJob.set(key, values)
  }
  const groups = new Map<string, { key: string; name: string; grams: number; jobIds: Set<string>; eventIds: Set<string>; errorJobIds: Set<string> }>()
  const seenJobs = new Set<string>()
  let unknownGrams = 0
  for (const record of filterUsage(records, from, to)) {
    const jobId = record.id.toUpperCase()
    if (record.state !== 'applied' || seenJobs.has(jobId)) continue
    seenJobs.add(jobId)
    for (const row of record.rows) {
      if ((spoolId && row.spoolId !== spoolId) || (colorId && row.colorId !== colorId)) continue
      const key = dimension === 'spool' ? row.spoolId : row.colorId
      if (!key) { unknownGrams += row.grams; continue }
      let group = groups.get(key)
      if (!group) {
        group = { key, name: dimension === 'spool' ? row.name || key : row.colorName || key, grams: 0, jobIds: new Set(), eventIds: new Set(), errorJobIds: new Set() }
        groups.set(key, group)
      }
      group.grams += row.grams
      group.jobIds.add(jobId)
      for (const event of eventsByJob.get(jobId) || []) {
        const linked = event.spools.some(link => link.spoolId === row.spoolId &&
          (!(dimension === 'color' || colorId) || link.colorId === row.colorId))
        if (!linked) continue
        group.eventIds.add(event.id)
        group.errorJobIds.add(jobId)
      }
    }
  }
  const rows = [...groups.values()].map(group => ({
    key: group.key, name: group.name, grams: group.grams, jobs: group.jobIds.size,
    messages: group.eventIds.size, errorJobs: group.errorJobIds.size,
    perKg: group.grams > 0 ? group.eventIds.size * 1000 / group.grams : null
  }))
  return { rows, unknownGrams }
}

'use strict'
// New configurable periods are calculated once by the Python maintenance module,
// including timezone/calendar rules. Missing/stale status must not bypass an opt-out.
function maintenanceStatus (m, published, now = Date.now() / 1000) {
  const fresh = published && published.revision === m.revision &&
    Number.isFinite(published.checkedAt) && now >= published.checkedAt && now - published.checkedAt < 90
  if (m.periods) return {
    serviceDue: m.periods.service?.enabled === true && fresh ? published.serviceDue === true : false,
    bedDue: m.bedEnabled === true && m.periods.bed?.enabled === true && fresh ? published.bedDue === true : false
  }
  if (fresh) return { serviceDue: published.serviceDue === true, bedDue: m.bedEnabled && published.bedDue === true }
  // Compatibility with an older worker until both parts have been updated.
  const elapsed = m.baseSeconds + Object.values(m.jobs).reduce((sum, j) => sum + j.seconds, 0)
  const completed = Object.values(m.jobs).filter(j => j.completed).length
  const marker = m.service
  let serviceDue = !marker
  if (marker) {
    const d = new Date(marker.time * 1000); const day = d.getUTCDate()
    d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() + 1)
    const max = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate()
    d.setUTCDate(Math.min(day, max))
    serviceDue = elapsed - marker.seconds >= 360000 || now * 1000 >= d.getTime()
  }
  return { serviceDue, bedDue: m.bedEnabled && (!m.bed || elapsed - m.bed.seconds >= 36000 || completed - m.bed.completed >= 5) }
}
module.exports = { maintenanceStatus }

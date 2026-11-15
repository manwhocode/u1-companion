const test = require('node:test')
const assert = require('node:assert/strict')
const { maintenanceStatus } = require('./maintenance-status.cjs')
const m = () => ({ revision: 'a', baseSeconds: 0, jobs: {}, bedEnabled: true, service: null, bed: null,
  periods: { service: { enabled: true }, bed: { enabled: true } } })
test('honors disabled notifications even when a previous published state was due', () => {
  const v = m(); v.periods.service.enabled = v.periods.bed.enabled = false
  assert.deepEqual(maintenanceStatus(v, { revision: 'a', checkedAt: 100, serviceDue: true, bedDue: true }, 110), { serviceDue: false, bedDue: false })
})
test('uses fresh status for custom periods and refuses stale/mismatched data', () => {
  const p = { revision: 'a', checkedAt: 100, serviceDue: true, bedDue: false }
  assert.deepEqual(maintenanceStatus(m(), p, 110), { serviceDue: true, bedDue: false })
  assert.deepEqual(maintenanceStatus(m(), p, 200), { serviceDue: false, bedDue: false })
  assert.deepEqual(maintenanceStatus(m(), { ...p, revision: 'old' }, 110), { serviceDue: false, bedDue: false })
  assert.deepEqual(maintenanceStatus(m(), null, 110), { serviceDue: false, bedDue: false })
})
test('keeps compatibility with legacy reminders without new settings', () => {
  const v = m(); delete v.periods
  assert.deepEqual(maintenanceStatus(v, null, 110), { serviceDue: true, bedDue: true })
})

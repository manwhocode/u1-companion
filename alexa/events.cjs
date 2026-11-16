'use strict'
const crypto = require('node:crypto')
const hash = value => crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex')
const phrases = {
  started: 'Your print has started.', calibrationStarted: 'Filament calibration has started.', calibrationCompleted: 'Filament calibration is complete.', calibrationStopped: 'Filament calibration has stopped. Please check the printer.',
  finished: 'Your print has finished.', stopped: 'Your print has stopped.', paused: 'Your print is paused.', resumed: 'Your print has resumed.',
  error: 'Your printer reported an error. Please check the printer.', repeat: 'Your printer still needs attention. The error has not been cleared.', recovered: 'The printer error has cleared.',
  shortage: 'A filament spool may run out in about thirty minutes. Please check the printer.',
  maintenance: 'Your printer requires maintenance.', bed: 'Bed calibration is recommended.', companionUpdate: 'A new U1 Companion update is available.',
  dryerDone: 'Filament drying is complete.', dryerPaused: 'Filament drying has paused and bed heating has been turned off.',
  scheduleFailed: 'Your scheduled print could not start. Please check the printer.'
}
function reduce (old, snapshot, now) {
  const state = JSON.parse(JSON.stringify(old || { previous: null, errors: {}, once: {} }))
  const events = []
  const add = (kind, id) => events.push({ kind, id: hash([kind, id]), time: now })
  const previous = state.previous
  const current = snapshot.print || {}
  const sameJob = previous && previous.job === snapshot.job
  if (previous && snapshot.job && current.state === 'printing' && previous.job !== snapshot.job) {
    const key = 'started:' + snapshot.job
    if (!state.once[key]) { state.once[key] = now; add('started', snapshot.job) }
  }
  const calibration = snapshot.calibration || {}
  const calibrationActive = ['starting','loading','calibrating','saving','finishing'].includes(calibration.state)
  if (previous && calibration.id) {
    let kind
    if (calibrationActive && previous.calibrationId !== calibration.id) kind = 'calibrationStarted'
    if (previous.calibrationId === calibration.id && previous.calibrationState !== calibration.state) {
      if (calibration.state === 'completed') kind = 'calibrationCompleted'
      if (['stopped','failed','interrupted'].includes(calibration.state)) kind = 'calibrationStopped'
    }
    const key = kind + ':' + calibration.id
    if (kind && !state.once[key]) { state.once[key] = now; add(kind, calibration.id) }
  }
  if (previous && sameJob && previous.printState !== current.state) {
    if (current.state === 'complete') add('finished', snapshot.job)
    if (['cancelled', 'error'].includes(current.state)) add('stopped', snapshot.job)
    if (current.state === 'paused') add('paused', [snapshot.job, now])
    if (current.state === 'printing' && previous.printState === 'paused') add('resumed', [snapshot.job, now])
  }
  const active = new Set()
  for (const error of snapshot.errors || []) {
    const key = hash(error); active.add(key)
    if (!state.errors[key]) { state.errors[key] = { first: now, repeated: false }; add('error', key) }
    else if (!state.errors[key].repeated && now - state.errors[key].first >= 900) { state.errors[key].repeated = true; add('repeat', key) }
  }
  for (const key of Object.keys(state.errors)) if (!active.has(key)) { add('recovered', [key, now]); delete state.errors[key] }
  if (previous && snapshot.dryerNotify !== false && snapshot.dryer?.state === 'completed' && previous.dryerState !== 'completed') add('dryerDone', snapshot.dryerSession)
  if (previous && snapshot.dryerNotify !== false && snapshot.dryer?.state === 'paused' && previous.dryerState !== 'paused') add('dryerPaused', [snapshot.dryerSession, now])
  if (previous && ['blocked', 'needs_review'].includes(snapshot.schedule?.state) && previous.scheduleVersion !== snapshot.scheduleVersion) add('scheduleFailed', snapshot.scheduleVersion)
  for (const row of snapshot.shortages || []) {
    if (Number.isFinite(row.seconds) && row.seconds >= 0 && row.seconds <= 1800 && row.shortage > 0 && !snapshot.paused) {
      const key = 'shortage:' + snapshot.job + ':' + row.head
      if (!state.once[key]) { state.once[key] = now; add('shortage', key) }
    }
  }
  for (const kind of ['maintenance', 'bed']) {
    const marker = snapshot[kind]
    if (marker?.due) {
      const key = kind + ':' + marker.revision
      // First due warning and one reminder per new print job, no 5-second loop.
      if (!state.once[key] || (snapshot.job && previous?.job !== snapshot.job && current.state === 'printing')) { state.once[key] = now; add(kind, [key, snapshot.job]) }
    }
  }
  const update = snapshot.companionUpdate
  if (update?.updateAvailable && !update.checkFailed && update.latest && now - update.updatedAt < 7200 && state.lastCompanionUpdate !== update.latest) {
    state.lastCompanionUpdate = update.latest; add('companionUpdate', update.latest)
  }
  const entries = Object.entries(state.once).sort((a,b) => b[1] - a[1]).slice(0,200)
  state.once = Object.fromEntries(entries)
  state.previous = { job: snapshot.job, printState: current.state, dryerState: snapshot.dryer?.state, scheduleVersion: snapshot.scheduleVersion, calibrationId:calibration.id, calibrationState:calibration.state }
  return { state, events }
}
module.exports = { phrases, reduce, hash }

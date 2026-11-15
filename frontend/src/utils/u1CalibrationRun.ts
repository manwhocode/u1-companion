import { u1t } from '@/plugins/i18n'
export interface CalibrationSensor { enabled?: boolean; filament_detected?: boolean }
export interface CalibrationStatus {
  webhooks?: { state: string }
  print_stats?: { state: string }
  idle_timeout?: { state: string }
  machine_state_manager?: { main_state: number | string; action_code: number | string }
  exception_manager?: { exceptions: unknown[] }
  print_task_config?: { filament_type: string[]; filament_color_rgba: string[] }
  [key: string]: unknown
}
export interface CalibrationLog { time: number; message: string; type: string }
export const calibrationQuery = '/printer/objects/query?webhooks&print_stats&idle_timeout&machine_state_manager&exception_manager&print_task_config&extruder&extruder1&extruder2&extruder3&filament_feed%20left&filament_feed%20right&filament_motion_sensor%20e0_filament&filament_motion_sensor%20e1_filament&filament_motion_sensor%20e2_filament&filament_motion_sensor%20e3_filament'

interface CalibrationFeeder { module_exist: boolean; filament_detected: boolean; disable_auto: boolean; channel_state: string; channel_error: string; channel_error_state: string }
export function calibrationHeadLoaded (status: CalibrationStatus, slot: number) {
  const sensor = status[`filament_motion_sensor e${slot}_filament`] as CalibrationSensor | undefined
  return sensor?.enabled === true && sensor.filament_detected === true
}

export function calibrationHeadReason (status: CalibrationStatus, slot: number): string {
  const material = status.print_task_config?.filament_type[slot]?.trim().toUpperCase()
  const module = status[slot < 2 ? 'filament_feed left' : 'filament_feed right'] as Record<string, CalibrationFeeder> | undefined
  const feeder = module?.[`extruder${slot}`]
  // TPU may be fed manually, bypassing the external feeder.
  if (material === 'TPU' && calibrationHeadLoaded(status, slot)) return ''
  // For all materials (including TPU), the feeder is the admission sensor.
  if (!feeder?.module_exist || feeder.filament_detected !== true) return material === 'TPU' ? u1t("Нет филамента в головке или податчике") : u1t("Нет филамента в податчике")
  if (!material || material === 'NONE') return u1t("Укажите материал филамента")
  if (!calibrationHeadLoaded(status, slot)) {
    if (feeder.disable_auto !== false) return u1t("Требуется ручная загрузка в головку")
    if (feeder.channel_error !== 'ok' || feeder.channel_error_state !== 'none') return u1t("Сначала устраните ошибку податчика")
    if (!['preload_finish', 'load_finish'].includes(feeder.channel_state)) return u1t("Податчик ещё не готов к загрузке")
  }
  return ''
}

export function assertCalibrationIdle (status: CalibrationStatus) {
  if (status.webhooks?.state !== 'ready' || !['Idle', 'Ready'].includes(status.idle_timeout?.state || '') ||
      !['standby', 'complete', 'cancelled'].includes(status.print_stats?.state || '') ||
      ![0, 'IDLE'].includes(status.machine_state_manager?.main_state ?? -1) ||
      ![0, 'IDLE'].includes(status.machine_state_manager?.action_code ?? -1) ||
      !status.exception_manager || status.exception_manager.exceptions.length) {
    throw new Error(u1t("Калибровка доступна только на свободном принтере без активных ошибок."))
  }
}

export function nativeCalibrationScript (slot: number) {
  if (!Number.isInteger(slot) || slot < 0 || slot > 3) throw new Error(u1t("Неверная головка"))
  // A0 explicitly selects the physical head, regardless of the slicer's tool map.
  // FLOW_CALIBRATE uses the active head and its stock material parameters.
  return `T${slot} A0\nFLOW_CALIBRATE\nM400`
}

export function nativeCalibrationLoadScript (slot: number) {
  nativeCalibrationScript(slot)
  return `AUTO_FEEDING EXTRUDER=${slot} LOAD=1\nM400`
}

export function measuredCalibrationK (logs: CalibrationLog[], marker: number, slot: number): number {
  const name = slot === 0 ? 'extruder' : `extruder${slot}`
  const fresh = logs.filter(row => row.time > marker)
  const start = fresh.findIndex(row => row.type === 'response' && row.message.trim() === `// start flow calibration for ${name}`)
  if (start < 0) throw new Error(u1t("Начало калибровки выбранной головки не подтверждено журналом."))
  const measured = fresh.slice(start + 1)
  if (measured.some(row => /abort calibration|flow k is out of range|^!!|start flow calibration for /i.test(row.message))) {
    throw new Error(u1t("Калибровка прервана или использовано штатное значение по умолчанию. Результат в библиотеку не записан."))
  }
  const results = measured.filter(row => row.type === 'response').map(row => row.message.match(/^\/\/ Got pressure advance: ([0-9.eE+-]+)\s*$/)).filter(Boolean)
  const value = results.length === 1 ? Number(results[0]?.[1]) : NaN
  if (!Number.isFinite(value) || value < 0 || value > 1) throw new Error(u1t("Измеренный K не подтверждён журналом. Проверьте консоль принтера."))
  return value
}

interface CalibrationIO {
  status: () => Promise<CalibrationStatus>
  logs: () => Promise<CalibrationLog[]>
  execute: (script: string) => Promise<void>
  stopped: () => boolean
  before: (slot: number, status: CalibrationStatus) => Promise<void>
  result: (slot: number, value: number) => Promise<void>
  wait: () => Promise<void>
  phase?: (slot: number, phase: 'load' | 'calibrate') => void
}

async function settledStatus (io: CalibrationIO) {
  let state = await io.status()
  for (let attempt = 0; attempt < 40 && state.idle_timeout?.state === 'Printing' &&
      ['standby', 'complete', 'cancelled'].includes(state.print_stats?.state || '') &&
      [0, 'IDLE'].includes(state.machine_state_manager?.main_state ?? -1); attempt++) {
    await io.wait()
    state = await io.status()
  }
  assertCalibrationIdle(state)
  return state
}

export async function runSelectedCalibrations (slots: number[], io: CalibrationIO) {
  if (!slots.length || slots.length > 4 || new Set(slots).size !== slots.length) throw new Error(u1t("Выберите головки для калибровки."))
  slots.forEach(nativeCalibrationScript)
  const initial = await io.status()
  assertCalibrationIdle(initial)
  for (const slot of slots) {
    const reason = calibrationHeadReason(initial, slot)
    if (reason) throw new Error(u1t("Головка {p0}: {p1}", { p0: slot + 1, p1: reason }))
  }
  for (const slot of [...slots].sort()) {
    if (io.stopped()) break
    const status = await io.status()
    assertCalibrationIdle(status)
    const reason = calibrationHeadReason(status, slot)
    if (reason) throw new Error(u1t("Головка {p0}: {p1}", { p0: slot + 1, p1: reason }))
    const signature = (state: CalibrationStatus) => `${state.print_task_config?.filament_type[slot]}:${state.print_task_config?.filament_color_rgba[slot]}`
    if (signature(status) !== signature(initial)) throw new Error(u1t("Головка {p0}: материал или цвет изменились. Откройте запуск заново.", { p0: slot + 1 }))
    await io.before(slot, status)
    // Final sensor/state check immediately before the only physical command.
    let ready = await io.status()
    assertCalibrationIdle(ready)
    if (calibrationHeadReason(ready, slot) || signature(ready) !== signature(status)) throw new Error(u1t("Головка {p0}: филамент или состояние изменились. Запуск отменён.", { p0: slot + 1 }))
    if (io.stopped()) break
    if (!calibrationHeadLoaded(ready, slot)) {
      const sensor = ready[`filament_motion_sensor e${slot}_filament`] as CalibrationSensor | undefined
      if (sensor?.enabled !== true) throw new Error(u1t("Головка {p0}: невозможно подтвердить загрузку — датчик головки недоступен или выключен.", { p0: slot + 1 }))
      io.phase?.(slot, 'load')
      await io.execute(nativeCalibrationLoadScript(slot))
      ready = await settledStatus(io)
      if (!calibrationHeadLoaded(ready, slot)) throw new Error(u1t("Головка {p0}: штатная загрузка не подтверждена датчиком. Калибровка не запущена.", { p0: slot + 1 }))
      if (signature(ready) !== signature(status)) throw new Error(u1t("Головка {p0}: материал или цвет изменились при загрузке. Калибровка не запущена.", { p0: slot + 1 }))
      if (io.stopped()) break
    }
    const marker = Math.max(0, ...(await io.logs()).map(row => row.time))
    ready = await io.status()
    assertCalibrationIdle(ready)
    if (!calibrationHeadLoaded(ready, slot) || signature(ready) !== signature(status)) throw new Error(u1t("Головка {p0}: загрузка или материал изменились. Калибровка отменена.", { p0: slot + 1 }))
    io.phase?.(slot, 'calibrate')
    await io.execute(nativeCalibrationScript(slot))
    const value = measuredCalibrationK(await io.logs(), marker, slot)
    const after = await settledStatus(io)
    const object = after[slot === 0 ? 'extruder' : `extruder${slot}`] as {pressure_advance?: number} | undefined
    if (typeof object?.pressure_advance !== 'number' || Math.abs(object.pressure_advance - value) > 0.000001) {
      throw new Error(u1t("Головка {p0}: значение K в принтере не совпало с измеренным. Очередь остановлена.", { p0: slot + 1 }))
    }
    await io.result(slot, value)
  }
}

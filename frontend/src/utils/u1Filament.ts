import { u1t } from '@/plugins/i18n'
export const materials = ['PLA', 'PETG', 'ABS', 'ASA', 'TPU', 'PVA', 'PA', 'PC']
import type { FilamentCalibration } from './u1Calibration'
export interface FilamentPreset { material: string; hex: string; manufacturer?: string; calibration?: FilamentCalibration }

export function groupFilaments<T extends Pick<FilamentPreset, 'material' | 'manufacturer'>> (entries: readonly T[]) {
  const manufacturers = new Map<string, Map<string, T[]>>()
  for (const entry of entries) {
    const manufacturer = entry.manufacturer?.trim() || u1t("Без производителя")
    const material = entry.material?.trim().toUpperCase() || u1t("Без материала")
    let byMaterial = manufacturers.get(manufacturer)
    if (!byMaterial) {
      byMaterial = new Map()
      manufacturers.set(manufacturer, byMaterial)
    }
    const group = byMaterial.get(material)
    if (group) group.push(entry)
    else byMaterial.set(material, [entry])
  }
  return [...manufacturers].sort(([a], [b]) => a.localeCompare(b, 'ru')).map(([name, byMaterial]) => {
    const materials = [...byMaterial].sort(([a], [b]) => a.localeCompare(b, 'ru'))
      .map(([name, entries]) => ({ name, entries }))
    return { name, materials, count: materials.reduce((total, material) => total + material.entries.length, 0) }
  })
}

export interface TaskConfig {
  filament_exist: boolean[]
  filament_edit: boolean[]
  filament_color_rgba: string[]
  filament_type: string[]
  filament_vendor: string[]
}
export function validatePreset (preset: FilamentPreset): FilamentPreset {
  const hex = preset.hex.trim().replace(/^#/, '').toUpperCase()
  if (!/^[0-9A-F]{6}$/.test(hex)) throw new Error(u1t("HEX: введите 6 символов, например #39FF14"))
  if (!materials.includes(preset.material)) throw new Error(u1t("Выберите поддерживаемый материал"))
  return { material: preset.material, hex: '#' + hex, ...(preset.manufacturer ? { manufacturer: String(preset.manufacturer).trim().slice(0, 80) } : {}) }
}
export function parseQr (raw: string): FilamentPreset {
  let text = String(raw).replace(/^\uFEFF/, '').trim()
  if (/^u1filament%3a/i.test(text)) text = decodeURIComponent(text)
  if (/^u1spool:/i.test(text)) throw new Error(u1t("Прочитана метка Hub с ID катушки. В ней нет материала и цвета; нужна этикетка, созданная этой страницей."))
  let body: string
  if (/^u1filament:/i.test(text)) body = text.slice('u1filament:'.length)
  else if (text.startsWith('{')) body = text
  else throw new Error(u1t("QR найден, но это не этикетка филамента. Прочитано: ") + text.slice(0, 120))
  const parsed = JSON.parse(body)
  if (!parsed || typeof parsed !== 'object' || !('material' in parsed) || !('hex' in parsed) || typeof parsed.material !== 'string' || typeof parsed.hex !== 'string') throw new Error(u1t("QR не содержит материал и HEX"))
  const data = parsed as FilamentPreset
  return validatePreset({ material: data.material, hex: data.hex, manufacturer: typeof data.manufacturer === 'string' ? data.manufacturer : undefined })
}
export function assertWritable (slot: number, state: string, task: TaskConfig) {
  if (!Number.isInteger(slot) || slot < 0 || slot > 3) throw new Error(u1t("Неверная головка"))
  if (!['standby', 'complete', 'cancelled'].includes(state)) throw new Error(u1t("Изменение разрешено только в простое, после завершения или отмены печати"))
  if (task.filament_exist?.[slot] !== true) throw new Error(u1t("В этой головке нет филамента"))
  if (task.filament_edit?.[slot] !== true) throw new Error(u1t("Редактирование не разрешено принтером (RFID или неизвестный статус)"))
}
export function commands (slot: number, preset: FilamentPreset) {
  if (!Number.isInteger(slot) || slot < 0 || slot > 3) throw new Error(u1t("Неверная головка"))
  const p = validatePreset(preset)
  return [
    `SET_PRINT_FILAMENT_CONFIG CONFIG_EXTRUDER=${slot} VENDOR=Snapmaker FILAMENT_TYPE=${p.material} FILAMENT_SUBTYPE='Basic'`,
    `SET_PRINT_FILAMENT_CONFIG CONFIG_EXTRUDER='${slot}' FILAMENT_COLOR_RGBA='${p.hex.slice(1)}FF' SAVE='1'`
  ]
}

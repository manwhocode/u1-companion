import { u1t } from '@/plugins/i18n'
export interface FilamentCalibration {
  pressureAdvance?: number
  flowRatio?: number
  date: string
  method: string
  notes?: string
}

export function calibrationNumber (input: string, maximum: number, positive = false): number | undefined {
  if (!input.trim()) return undefined
  const value = Number(input.trim().replace(',', '.'))
  if (!Number.isFinite(value) || value < 0 || value > maximum || (positive && value === 0)) {
    throw new Error(positive ? u1t("Введите число больше 0 и не больше {p0}", { p0: maximum }) : u1t("Введите число от 0 до {p0}", { p0: maximum }))
  }
  return value
}

export function calibrationSummary (value?: FilamentCalibration) {
  return u1t("K: {p0}", { p0: value?.pressureAdvance ?? u1t("не задан") })
}

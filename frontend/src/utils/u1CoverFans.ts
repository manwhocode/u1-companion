import { u1t } from '@/plugins/i18n'
export interface Cover { power_detected: boolean; mode: number; desired_chamber_temp: number; critical_chamber_temp: number; exhaust_fan: { speed: number; speed_threshold: number }; inner_fan: { speed: number; delay: number } }
export function coverCommand (p: Cover, fan: 'exhaust' | 'inner', percent: number): string {
  if (!p.power_detected) throw new Error(u1t("Крышка не подключена."))
  if (!Number.isInteger(percent) || percent < 0 || percent > 100) throw new Error(u1t("Скорость должна быть от 0 до 100%."))
  if (![0, 1].includes(p.mode)) throw new Error(u1t("Во время прогрева камеры управление остаётся штатным."))
  if (fan === 'inner') return `SET_PURIFIER FAN=inner SPEED=${percent / 100}`
  if (p.mode === 0) return `SET_PURIFIER FAN=exhaust SPEED=${percent / 100}`
  const { desired_chamber_temp: desired, critical_chamber_temp: critical } = p
  if (!Number.isFinite(desired) || !Number.isFinite(critical) || desired <= 0 || critical <= desired) throw new Error(u1t("Не подтверждены температурные защиты камеры."))
  return `SET_PURIFIER_MODE MODE=1 DESIRE_TEMP=${desired} ALARM_TEMP=${critical} FAN_SPEED=${percent / 100} DYNAMIC_FAN_CONTROL=1`
}

import { describe, it, expect } from 'vitest'
import { assertWritable, commands, parseQr, validatePreset, type TaskConfig } from '../../src/utils/u1Filament'
const task: TaskConfig = { filament_exist: [true], filament_edit: [true], filament_color_rgba: ['000000FF'], filament_type: ['PLA'], filament_vendor: ['Snapmaker'] }
describe('U1 filament safety', () => {
  it('blocks printing, paused, error and unknown states', () => {
    for (const state of ['printing', 'paused', 'error', '', 'unknown']) expect(() => assertWritable(0, state, task)).toThrow()
  })
  it('requires loaded and explicitly writable slot', () => {
    expect(() => assertWritable(0, 'standby', task)).not.toThrow()
    expect(() => assertWritable(1, 'standby', task)).toThrow()
    expect(() => assertWritable(0, 'standby', { ...task, filament_edit: [false] })).toThrow()
  })
  it('never accepts commands or arbitrary materials from QR/HEX', () => {
    for (const hex of ['red', '#FFF', "FFFFFF\nG28", 'FFFFFFFF']) expect(() => validatePreset({ material: 'PLA', hex })).toThrow()
    expect(() => parseQr('https://example.com')).toThrow()
    expect(() => parseQr('u1spool:123')).toThrow()
    expect(() => parseQr('u1filament:{"material":"PLA;G28","hex":"FFFFFF"}')).toThrow()
  })
  it('normalizes QR and emits only the two verified metadata commands', () => {
    const p = parseQr('u1filament:{"material":"PLA","hex":"39ff14"}')
    expect(p.hex).toBe('#39FF14')
    expect(commands(0, p)).toEqual(["SET_PRINT_FILAMENT_CONFIG CONFIG_EXTRUDER=0 VENDOR=Snapmaker FILAMENT_TYPE=PLA FILAMENT_SUBTYPE='Basic'", "SET_PRINT_FILAMENT_CONFIG CONFIG_EXTRUDER='0' FILAMENT_COLOR_RGBA='39FF14FF' SAVE='1'"])
    expect(() => commands(4, p)).toThrow()
  })
})

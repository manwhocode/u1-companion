import { afterEach, expect, it, vi } from 'vitest'
import U1MagnetPause from '@/components/U1MagnetPause.vue'
import { u1DataRequest } from '@/utils/u1DataClient'

vi.mock('@/utils/u1DataClient', () => ({ u1DataRequest: vi.fn() }))
afterEach(() => { vi.restoreAllMocks(); vi.mocked(u1DataRequest).mockReset() })
const state = () => ({ available: true, state: 'idle', runtimeJob: 'job-a', printState: 'printing', currentFilename: 'a.gcode', currentLayer: 3 })
it('opening the manual dialog captures the job without moving the printer', () => {
  const vm = new U1MagnetPause(); vm.state = state(); vm.openManual()
  expect(vm.manualOpen).toBe(true); expect(vm.manualJob).toBe('job-a'); expect(vm.manualConfirmed).toBe(false)
  expect(u1DataRequest).not.toHaveBeenCalled(); vm.$destroy()
})
it('manual lowering needs explicit confirmation', async () => {
  const vm = new U1MagnetPause(); vm.state = state(); vm.openManual(); await vm.lower()
  expect(u1DataRequest).not.toHaveBeenCalled(); vm.$destroy()
})
it('polling preserves layer input, file selection, and consent', async () => {
  const vm = new U1MagnetPause(); vm.layers = '12, 24 36'; vm.filename = 'next.gcode'; vm.confirmed = true
  vi.mocked(u1DataRequest).mockResolvedValue(state()); await vm.load()
  expect(vm.layers).toBe('12, 24 36'); expect(vm.filename).toBe('next.gcode'); expect(vm.confirmed).toBe(true); vm.$destroy()
})
it('unconfirmed plans are never armed and stopped plans have no next-layer hint', async () => {
  const vm = new U1MagnetPause(); vm.state = { ...state(), state: 'cancelled', layers: [12,24], done: [] }; vm.plan = { token: 'a' }
  await vm.arm(); expect(u1DataRequest).not.toHaveBeenCalled(); expect(vm.nextLayer).toBeUndefined(); vm.$destroy()
})
it('current-print tab captures the running file and job without a file picker or writes', () => {
  const vm = new U1MagnetPause(); vm.state = state(); vm.filename = 'next.gcode'; vm.layers = '12, 24'
  vm.switchMode('current')
  expect(vm.filename).toBe('a.gcode'); expect(vm.planJob).toBe('job-a'); expect(vm.modeReason).toBe('')
  expect(vm.layers).toBe('12, 24'); expect(u1DataRequest).not.toHaveBeenCalled()
  vm.switchMode('next'); expect(vm.filename).toBe('next.gcode'); expect(vm.modeReason).not.toBe(''); vm.$destroy()
})
it('preparing pauses for a running print uses its captured instance', async () => {
  const vm = new U1MagnetPause(); vm.state = state(); vm.switchMode('current'); vm.layers = '12 24'
  vi.mocked(u1DataRequest).mockResolvedValue({ token: 'preview', layers: [12,24] }); await vm.prepare()
  expect(u1DataRequest).toHaveBeenCalledWith('magnet_prepare', { filename: 'a.gcode', layers: '12 24', mode: 'current', job: 'job-a' }, 60000)
  vm.$destroy()
})
it('changed jobs block submission instead of silently applying pauses to another print', async () => {
  const vm = new U1MagnetPause(); vm.state = state(); vm.switchMode('current'); vm.layers = '12'
  vm.state = { ...state(), runtimeJob: 'job-b' }; await vm.prepare()
  expect(vm.modeReason).not.toBe(''); expect(u1DataRequest).not.toHaveBeenCalled(); vm.$destroy()
})
it('switching tabs invalidates preview and confirmation without sending commands', () => {
  const vm = new U1MagnetPause(); vm.state = { ...state(), printState: 'standby' }; vm.plan = { token: 'old' }; vm.confirmed = true
  vm.switchMode('current'); expect(vm.plan).toBe(null); expect(vm.confirmed).toBe(false); expect(vm.modeReason).toBe('Сейчас печать не идёт. Запустите её с ПК или приложения, затем откройте эту вкладку.')
  expect(u1DataRequest).not.toHaveBeenCalled(); vm.$destroy()
})

it('clears timeout only for confirmed matching request',async()=>{const vm=new U1MagnetPause();vm.error='timed out';vm.pendingAck={action:'arm',token:'mine'};vi.mocked(u1DataRequest).mockResolvedValue({...state(),state:'active',token:'other'});await vm.load();expect(vm.error).toBe('timed out');vi.mocked(u1DataRequest).mockResolvedValue({...state(),state:'active',token:'mine'});await vm.load();expect(vm.error).toBe('');vm.$destroy()})
it('does not hide validation errors',async()=>{const vm=new U1MagnetPause();vm.error='invalid file';vm.pendingAck={action:'arm',token:'mine'};vi.mocked(u1DataRequest).mockResolvedValue({...state(),state:'active',token:'mine'});await vm.load();expect(vm.error).toBe('invalid file');vm.$destroy()})

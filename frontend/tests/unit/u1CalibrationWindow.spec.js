import { afterEach, expect, it, vi } from 'vitest'
import U1CalibrationRunner from '@/components/U1CalibrationRunner.vue'
import { u1DataRequest } from '@/utils/u1DataClient'

vi.mock('@/utils/u1DataClient', () => ({ u1DataRequest: vi.fn() }))
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); vi.mocked(u1DataRequest).mockReset() })

it('can close while a state request is pending and ignores its late result', async () => {
  vi.useFakeTimers()
  let finish
  vi.mocked(u1DataRequest).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  const vm = new U1CalibrationRunner()
  vi.spyOn(vm, 'readStatus').mockResolvedValue({})
  vm.opened = true
  const request = vm.refresh()
  expect(vm.refreshing).toBe(true)
  vm.close()
  expect(vm.opened).toBe(false)
  expect(vm.refreshing).toBe(false)
  finish({ state: 'calibrating', activeSlot: 1, results: [] })
  await request
  expect(vm.opened).toBe(false)
  expect(vm.running).toBe(false)
  vm.$destroy()
})

it('ends the visible spinner after a bounded timeout', async () => {
  vi.useFakeTimers()
  vi.mocked(u1DataRequest).mockImplementation(() => new Promise(() => {}))
  const vm = new U1CalibrationRunner()
  vi.spyOn(vm, 'readStatus').mockResolvedValue({})
  vm.opened = true
  const request = vm.refresh()
  await vi.advanceTimersByTimeAsync(12001)
  await request
  expect(vm.refreshing).toBe(false)
  expect(vm.polling).toBe(false)
  expect(vm.message).toContain('12 секунд')
  vm.$destroy()
})

it('background polling never displays the manual refresh spinner', async () => {
  vi.useFakeTimers()
  vi.mocked(u1DataRequest).mockResolvedValue({ state: 'completed', results: [] })
  const vm = new U1CalibrationRunner()
  vi.spyOn(vm, 'readStatus').mockResolvedValue({})
  vm.opened = true
  const request = vm.refresh(true)
  expect(vm.refreshing).toBe(false)
  await request
  expect(vm.refreshing).toBe(false)
  vm.$destroy()
})

import { afterEach, expect, it, vi } from 'vitest'
import U1PrintPlayer from '@/components/U1PrintPlayer.vue'
import U1DataBackup from '@/components/U1DataBackup.vue'
import { u1DataRequest } from '@/utils/u1DataClient'
import { snapmakerReferralUrl } from '@/utils/snapmakerReferral'
vi.mock('@/utils/u1DataClient', () => ({ u1DataRequest: vi.fn() }))
afterEach(() => { vi.restoreAllMocks(); vi.mocked(u1DataRequest).mockReset() })
const paused = () => ({ ready: true, state: 'paused', filename: 'a.gcode', progress: 0.5, duration: 100, currentJob: 'job-a', reason: '', canStart: false, canPause: false, canResume: true, canCancel: true })

it('bed acknowledgement opens a separate manual confirmation without resuming', () => {
  const vm = new U1PrintPlayer(); vm.state = { ...paused(), canResume: false, canAcknowledgeBed: true }
  vm.confirm('ack_bed')
  expect(vm.pendingAction).toBe('ack_bed'); expect(vm.pendingJob).toBe('job-a'); expect(vm.confirmOpen).toBe(true)
  expect(u1DataRequest).not.toHaveBeenCalled(); vm.$destroy()
})

it('play on a paused print opens confirmation without sending a command', () => {
  const vm = new U1PrintPlayer(); vm.state = paused(); vm.play()
  expect(vm.confirmOpen).toBe(true); expect(vm.pendingAction).toBe('resume'); expect(vm.pendingJob).toBe('job-a')
  expect(u1DataRequest).not.toHaveBeenCalled(); vm.$destroy()
})
it('pause uses the captured job identity and the one-shot backend operation', async () => {
  const vm = new U1PrintPlayer(); vm.state = { ...paused(), state: 'printing', canPause: true, canResume: false }
  vi.spyOn(vm, 'load').mockResolvedValue(undefined); vi.mocked(u1DataRequest).mockResolvedValue({ message: 'accepted' })
  await vm.send('pause')
  expect(u1DataRequest).toHaveBeenCalledWith('print_player_action', { action: 'pause', currentJob: 'job-a', confirmed: false })
  expect(vm.busy).toBe(false); vm.$destroy()
})
it('status refresh preserves selected file and preparation options', async () => {
  const vm = new U1PrintPlayer(); vm.filename = 'next.gcode'; vm.mapping = [2, 1, 0, 3]; vm.confirmed = true
  vi.mocked(u1DataRequest).mockResolvedValue(paused()); await vm.load()
  expect(vm.filename).toBe('next.gcode'); expect(vm.mapping).toEqual([2, 1, 0, 3]); expect(vm.confirmed).toBe(true); vm.$destroy()
})
it('connection failure removes stale control availability', async () => {
  const vm = new U1PrintPlayer(); vm.state = paused()
  vi.mocked(u1DataRequest).mockRejectedValue(new Error('offline')); await vm.load()
  expect(vm.state).toBe(null); expect(vm.connectionError).toBe('offline'); vm.$destroy()
})
it('changing export scope invalidates the previously prepared share file', () => {
  const vm = new U1DataBackup(); vm.exported = { format: 'full', version: 1, createdAt: '', data: {} }; vm.clearExport()
  expect(vm.exported).toBe(null); expect(vm.downloadUrl).toBe(''); vm.$destroy()
})
it('partner links preserve the product variant and other query parameters', () => {
  const url = new URL(snapmakerReferralUrl('https://eu.snapmaker.com/products/snapspeed-pla-filament?variant=46217784393867&utm_source=u1#color'))
  expect(url.hostname).toBe('snapmaker-eu.myshopify.com'); expect(url.searchParams.get('ref')).toBe('i_v')
  expect(url.searchParams.get('variant')).toBe('46217784393867'); expect(url.hash).toBe('#color')
  expect(() => snapmakerReferralUrl('https://example.com/')).toThrow()
})

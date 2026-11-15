import { afterEach, describe, expect, it, vi } from 'vitest'
import U1Alexa from '@/components/U1Alexa.vue'
import { u1DataRequest } from '@/utils/u1DataClient'

vi.mock('@/utils/u1DataClient', () => ({ u1DataRequest: vi.fn() }))
const waiting = () => ({ phase: 'awaiting_login', message: '', devices: [], loginUrl: null, config: { region: 'amazon.de', method: 'announcement', enabled: false, targets: [], phrases: {} } })
const ready = () => ({ ...waiting(), externalLoginUrl: 'https://www.amazon.com/ap/signin?test=1' })

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.mocked(u1DataRequest).mockReset() })
describe('Alexa login preparation', () => {
  it('waits for a delayed link without opening or closing a popup', async () => {
    vi.useFakeTimers()
    const open = vi.spyOn(window, 'open')
    const vm = new U1Alexa()
    vi.spyOn(vm, 'secure', 'get').mockReturnValue(true)
    vm.state = waiting()
    vi.spyOn(vm, 'command').mockResolvedValue(undefined)
    vi.mocked(u1DataRequest).mockResolvedValue(ready())
    const pending = vm.loginWithPasskey()
    await vi.advanceTimersByTimeAsync(1000)
    await pending
    expect(vm.externalLink).toBe(ready().externalLoginUrl)
    expect(vm.error).toBe('')
    expect(vm.busy).toBe(false)
    expect(open).not.toHaveBeenCalled()
    vm.$destroy()
  })
  it('keeps a visible error when no link arrives instead of dismissing a window', async () => {
    vi.useFakeTimers()
    const open = vi.spyOn(window, 'open')
    const vm = new U1Alexa()
    vi.spyOn(vm, 'secure', 'get').mockReturnValue(true)
    vm.state = waiting()
    vi.spyOn(vm, 'command').mockResolvedValue(undefined)
    vi.mocked(u1DataRequest).mockResolvedValue(waiting())
    const pending = vm.loginWithPasskey()
    await vi.advanceTimersByTimeAsync(22000)
    await pending
    expect(vm.error).toContain('Amazon')
    expect(vm.busy).toBe(false)
    expect(open).not.toHaveBeenCalled()
    vm.$destroy()
  })
})
it('releases Alexa controls on a timeout without replaying the test', async () => {
  const vm = new U1Alexa()
  vi.mocked(u1DataRequest).mockRejectedValue(new Error('timeout'))
  await vm.test('device')
  expect(vm.busy).toBe(false)
  expect(vm.progress).toBe('')
  expect(vm.error).toContain('timeout')
  expect(u1DataRequest).toHaveBeenCalledTimes(1)
  vm.$destroy()
})
it('keeps only voice messages when loading legacy announcement settings', () => {
 const vm = new U1Alexa();vm.state = waiting();vm.sync();expect(vm.method).toBe('speak');vm.$destroy()
})

it('keeps language drafts and disables automatic speech until the new language is tested',()=>{
 const vm=new U1Alexa();vm.state={...waiting(),phase:'connected',speechCatalogs:{de:{started:'Druck gestartet'},en:{started:'Print started'}}};vm.phrases={started:'Custom phrase'};vm.language='de-DE';vm.enabled=true;vm.changeLanguage();expect(vm.phrases.started).toBe('Druck gestartet');expect(vm.enabled).toBe(false);vm.language='auto';vm.changeLanguage();expect(vm.phrases.started).toBe('Custom phrase');vm.$destroy()
})

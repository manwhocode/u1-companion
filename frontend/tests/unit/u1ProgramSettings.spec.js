import { u1t } from '@/plugins/i18n'
import { expect, it, vi } from 'vitest'
import Settings from '@/components/U1ProgramSettings.vue'
vi.mock('@/utils/u1DataClient', () => ({ u1DataRequest: vi.fn() }))
it('opens immediately without touching feeder configuration', async () => {
 const vm = new Settings(); const load = vi.spyOn(vm, 'load').mockResolvedValue()
 await vm.open(); expect(vm.opened).toBe(true); expect(load).not.toHaveBeenCalled()
 expect(vm.sectionNames).toHaveLength(8); expect(vm.sectionNames[6]).toBe(u1t('Управление через GPT'))
 vm.selectSection(6); expect(vm.section).toBe(6); expect(load).not.toHaveBeenCalled()
 vm.selectSection(5); expect(load).toHaveBeenCalledTimes(1); vm.$destroy()
})

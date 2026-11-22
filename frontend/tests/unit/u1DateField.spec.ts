import { afterEach, describe, expect, it, vi } from 'vitest'
import Field from '@/components/U1DateField.vue'
import i18n from '@/plugins/i18n'

const previous = i18n.locale
afterEach(() => { i18n.locale = previous })
describe('module date fields independent of browser language', () => {
  it('formats by interface locale and retains ISO model values', () => {
    const vm = new Field({i18n, propsData:{value:'2026-11-22'}})
    i18n.locale='en'; expect(vm.display).toBe('Nov 22, 2026')
    i18n.locale='de'; expect(vm.display).toBe('22.11.2026')
    expect(vm.value).toBe('2026-11-22'); vm.$destroy()
  })
  it('emits an unshifted date and clears a range filter', () => {
    const vm = new Field({i18n}); const emit=vi.spyOn(vm,'$emit')
    vm.opened=true; vm.selectDate('2026-11-22')
    expect(emit).toHaveBeenCalledWith('input','2026-11-22');expect(vm.opened).toBe(false)
    vm.clear();expect(emit).toHaveBeenCalledWith('input','');vm.$destroy()
  })
  it('retains local schedule time when choosing a date', () => {
    const vm = new Field({i18n,propsData:{value:'2026-11-21T09:45',datetime:true}});const emit=vi.spyOn(vm,'$emit')
    vm.selectDate('2026-11-22');expect(emit).toHaveBeenCalledWith('input','2026-11-22T09:45')
    vm.selectTime('10:30');expect(emit).toHaveBeenCalledWith('input','2026-11-21T10:30');vm.$destroy()
  })
})

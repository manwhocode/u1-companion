<template>
  <v-menu v-model="opened" :close-on-content-click="false" :disabled="disabled" offset-y max-width="340">
    <template #activator="{ on, attrs }">
      <v-text-field v-bind="{...$attrs, ...attrs}" :value="display" :label="label" :disabled="disabled" :clearable="clearable" readonly
        :placeholder="datetime ? 'YYYY-MM-DD HH:mm' : 'YYYY-MM-DD'" :append-icon="calendarIcon" v-on="on" @click:clear="clear" />
    </template>
    <v-card class="u1-date-calendar">
      <v-date-picker :value="date" :locale="$i18n.locale" no-title scrollable full-width @input="selectDate" />
      <v-time-picker v-if="datetime" :value="time" :disabled="!date" format="24hr" full-width @input="selectTime" />
      <v-card-actions><v-spacer /><v-btn text @click="opened = false">{{ $u1t('Закрыть') }}</v-btn></v-card-actions>
    </v-card>
  </v-menu>
</template>
<script lang="ts">
import Vue from 'vue'
import { mdiCalendar } from '@mdi/js'

// The browser/OS locale controls native date-input placeholders, regardless of
// the module language. Keep ISO model values but render our own localized picker.
export default Vue.extend({
  name: 'U1DateField',
  inheritAttrs: false,
  props: {
    value: {type: String, default: ''}, label: {type: String, default: ''},
    datetime: Boolean, disabled: Boolean, clearable: {type: Boolean, default: true}
  },
  data () { return {opened: false, calendarIcon: mdiCalendar} },
  computed: {
    date (): string { return /^\d{4}-\d{2}-\d{2}/.exec(this.value || '')?.[0] || '' },
    time (): string { return /T(\d{2}:\d{2})/.exec(this.value || '')?.[1] || '00:00' },
    display (): string {
      if (!this.date) return ''
      const value = new Date(this.date + 'T' + (this.datetime ? this.time : '12:00'))
      if (!Number.isFinite(value.getTime())) return ''
      return new Intl.DateTimeFormat(this.$i18n.locale, this.datetime ? {dateStyle:'medium', timeStyle:'short'} : {dateStyle:'medium'}).format(value)
    }
  },
  methods: {
    selectDate (value: string) { this.$emit('input', this.datetime ? value + 'T' + this.time : value); if (!this.datetime) this.opened = false },
    selectTime (value: string) { if (this.date) this.$emit('input', this.date + 'T' + value) },
    clear () { this.$emit('input', ''); this.opened = false }
  }
})
</script>
<style scoped>.u1-date-calendar {max-height:75vh;overflow-y:auto}</style>

<template><div><v-btn outlined @click="open">★ {{ $u1t('Избранные модели') }}</v-btn><v-dialog v-model="opened" max-width="760" scrollable content-class="u1-dialog u1-unified-dialog"><v-card><u1-dialog-close @close="opened = false" /><v-card-title>{{ $u1t('Избранные модели') }}</v-card-title><v-card-text><v-alert v-if="error" dense type="error">{{ error }}</v-alert><v-text-field v-model="name" :label="$u1t('Название')" outlined dense /><v-autocomplete v-model="selected" :items="files" multiple chips deletable-chips outlined dense :label="$u1t('G-code на принтере')" /><p>{{ $u1t('Объедините варианты одной модели с разными цветами.') }}</p><v-btn outlined :disabled="busy || !name.trim() || !selected.length" @click="save">{{ $u1t('Сохранить') }}</v-btn><v-divider class="my-3" /><div v-for="model in models" :key="model.id" class="mb-3"><strong>{{ model.name }}</strong><div>{{ model.files.join(', ') }}</div><v-btn small text @click="edit(model)">{{ $u1t('Изменить') }}</v-btn><v-btn small text :disabled="busy" @click="stats(model)">{{ $u1t('Статистика') }}</v-btn><v-btn small text :disabled="busy" @click="remove(model)">{{ $u1t('Удалить') }}</v-btn><v-btn small outlined @click="$emit('choose', model.files[0]); opened = false">{{ $u1t('Выбрать') }}</v-btn></div><v-card v-if="result" outlined class="pa-3"><strong>{{ result.model.name }}</strong><p>{{ $u1t('Печатей') }}: {{ result.prints }} · {{ $u1t('Завершено') }}: {{ result.completed }}</p><p>{{ $u1t('Время') }}: {{ (result.duration / 3600).toFixed(2) }} h · {{ $u1t('Списано') }}: {{ result.grams.toFixed(2) }} {{ $u1t('г') }} · {{ $u1t('Стоимость') }}: {{ result.priced ? result.cost.toFixed(2) : '—' }}</p><p>{{ $u1t('Статистика по сохранённой истории. Расход и стоимость — по журналу списаний.') }}</p><v-alert v-if="result.truncated" type="warning" dense>10000 · {{ $u1t('Заданий в журнале') }}</v-alert></v-card></v-card-text></v-card></v-dialog></div></template>
<script lang="ts">
import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
import { httpClientActions as http } from '@/api/httpClientActions'
interface Model {id:string;name:string;files:string[]}
interface Stats {model:Model;prints:number;completed:number;duration:number;grams:number;cost:number;priced:boolean;truncated:boolean}
@Component
export default class U1FavoriteModels extends Vue {
  opened = false; busy = false; error = ''; name = ''; id = ''; selected: string[] = []; files: string[] = []; models: Model[] = []; result: Stats | null = null
  async open () { this.opened = true; try { const f = await http.get<{result:{path:string}[]}>('/server/files/list?root=gcodes'); this.files = f.data.result.map(x => x.path).filter(x => x.toLowerCase().endsWith('.gcode')); await this.reload() } catch (e) { this.error = String(e) } }
  async reload () { this.models = (await u1DataRequest<{models:Model[]}>('models_state')).models }
  edit (m:Model) { this.id = m.id; this.name = m.name; this.selected = [...m.files] }
  async save () { await this.run('models_save', {id:this.id || undefined,name:this.name,files:this.selected}); this.id = ''; this.name = ''; this.selected = [] }
  async remove (m:Model) { if (await this.$confirm(m.name)) await this.run('models_delete', {id:m.id}) }
  async stats (m:Model) { this.busy = true; try { this.result = await u1DataRequest<Stats>('models_stats', {id:m.id}, 90000); this.error = '' } catch (e) { this.error = String(e) } finally { this.busy = false } }
  async run (op:string,payload:unknown) { this.busy = true; try { await u1DataRequest(op,payload); await this.reload(); this.error = ''; this.result = null } catch (e) { this.error = String(e) } finally { this.busy = false } }
}
</script>

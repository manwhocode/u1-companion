import copy, runpy, tempfile, unittest, uuid
from pathlib import Path
from u1_data_store import KEYS, DataStore, document, parse_document, partial_target, selected_data, state_from_raw

fixtures=runpy.run_path(str(Path(__file__).with_name('test-u1-data-store.py')),run_name='fixtures')
def data():
    raw=fixtures['sample_raw']()
    raw[KEYS['inventory']]['cores']=[{'id':'core','name':'Plastic spool','kind':'plastic','grams':200}]
    raw[KEYS['inventory']]['spools']=[{**fixtures['color']('spool'),'colorId':'color','coreId':'core','coreName':'Plastic spool','grams':1000,'tare':200,'accountedGrams':50}]
    raw[KEYS['inventory']]['heads']=['spool',None,None,None]
    raw[KEYS['usage']]['totals']={'spool':250}
    return state_from_raw(raw)

class Tests(unittest.TestCase):
    def test_colors_export_has_no_spools_usage_heads_or_cores(self):
        value=document(data(),'colors');self.assertEqual(value['format'],'u1-filament-selection')
        loaded=parse_document(value);self.assertEqual(len(loaded['library']['entries']),1)
        self.assertEqual(loaded['inventory']['spools'],[]);self.assertEqual(loaded['inventory']['cores'],[])
        self.assertEqual(loaded['usage']['totals'],{});self.assertEqual(loaded['reviews'],{})

    def test_cores_export_only_cores(self):
        value=parse_document(document(data(),'cores'))
        self.assertEqual(len(value['inventory']['cores']),1);self.assertEqual(value['library']['entries'],[])
        self.assertEqual(value['inventory']['spools'],[])

    def test_spools_export_normalizes_remaining_and_includes_only_dependencies(self):
        source=data();source['library']['entries'].append(fixtures['color']('unrelated'))
        value=parse_document(document(source,'spools'))
        self.assertEqual(value['inventory']['spools'][0]['grams'],800)
        self.assertEqual(value['inventory']['spools'][0]['accountedGrams'],0)
        self.assertEqual([c['id'] for c in value['library']['entries']],['color'])
        self.assertEqual(value['inventory']['heads'],[None]*4);self.assertEqual(value['usage']['totals'],{})
        self.assertEqual(source['inventory']['spools'][0]['grams'],1000)

    def test_colors_replace_preserves_spools_usage_and_linked_colors(self):
        current=data();incoming=state_from_raw(fixtures['sample_raw']());incoming['library']['entries']=[fixtures['color']('new')]
        target,_=partial_target(current,incoming,'colors','replace')
        self.assertEqual(target['inventory'],current['inventory']);self.assertEqual(target['usage'],current['usage'])
        self.assertEqual({c['id'] for c in target['library']['entries']},{'color','new'})

    def test_cores_replace_keeps_referenced_core_and_other_sections(self):
        current=data();incoming=state_from_raw(fixtures['sample_raw']())
        target,_=partial_target(current,incoming,'cores','replace')
        self.assertEqual(target,current)

    def test_spool_import_preserves_target_usage_and_current_remaining(self):
        current=state_from_raw(fixtures['sample_raw']());current['usage']['totals']={'spool':400}
        target,_=partial_target(current,parse_document(document(data(),'spools')),'spools','merge')
        row=target['inventory']['spools'][0]
        self.assertEqual(row['grams'],800);self.assertEqual(row['accountedGrams'],400)
        self.assertEqual(target['usage'],current['usage']);self.assertEqual(target['inventory']['heads'],[None]*4)
        repeated,_=partial_target(target,parse_document(document(data(),'spools')),'spools','merge')
        self.assertEqual(repeated,target)

    def test_colliding_dependency_id_does_not_overwrite_existing_color(self):
        current=state_from_raw(fixtures['sample_raw']());current['library']['entries'][0]['hex']='#FFFFFF'
        target,_=partial_target(current,parse_document(document(data(),'spools')),'spools','merge')
        self.assertEqual(target['library']['entries'][0]['hex'],'#FFFFFF')
        self.assertNotEqual(target['inventory']['spools'][0]['colorId'],'color')
        self.assertEqual(len(target['library']['entries']),2)

    def test_partial_file_full_choice_cannot_erase_other_sections(self):
        root=Path('local-backups/partial-data-tests');root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            api=fixtures['Api']();api.namespaces['fluidd'][KEYS['usage']]['totals']={'old':90}
            store=DataStore(api,folder);store.recover();before=copy.deepcopy(api.namespaces['fluidd'])
            preview=store.handle(str(uuid.uuid4()),{'operation':'preview','payload':{'document':document(data(),'cores'),'mode':'replace','scope':'full'}})
            self.assertEqual(preview['scope'],'cores')
            store.handle(str(uuid.uuid4()),{'operation':'import','payload':{'previewId':preview['previewId']}})
            after=api.namespaces['fluidd']
            self.assertEqual(after[KEYS['library']],before[KEYS['library']])
            self.assertEqual(after[KEYS['usage']],before[KEYS['usage']])
            self.assertEqual(len(after[KEYS['inventory']]['cores']),1)

    def test_scope_from_full_backup_imports_only_requested_part(self):
        current=data();incoming=copy.deepcopy(current);incoming['library']['entries'][0]['name']='Changed';incoming['usage']['totals']={'spool':900}
        target,_=partial_target(current,incoming,'colors','replace')
        self.assertEqual(target['library']['entries'][0]['name'],'Changed');self.assertEqual(target['usage'],current['usage'])

    def test_full_export_still_round_trips_and_invalid_scope_is_rejected(self):
        self.assertEqual(parse_document(document(data())),data())
        with self.assertRaises(ValueError):document(data(),'bad')
        value=document(data(),'colors');value['scope']='bad'
        with self.assertRaises(ValueError):parse_document(value)

if __name__=='__main__':unittest.main()

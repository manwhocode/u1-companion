import copy
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from u1_magnet_pause import U1MagnetPause, analyse, parse_layers, parking_delta, save, MAGNET_COMMANDS


SAMPLE = 'M83\nSET_PRINT_STATS_INFO TOTAL_LAYER=3 CURRENT_LAYER=0\n' + ''.join(
    ';LAYER_CHANGE\nSET_PRINT_STATS_INFO TOTAL_LAYER=3 CURRENT_LAYER=%d\nG1 X1 E1\n' % n for n in (1,2,3))


class Cmd:
    def __init__(self, **params): self.params = params
    def get(self, name, default=None): return self.params.get(name, default)
    def get_int(self, name, default=None): return int(self.params.get(name, default))
    def error(self, text): return ValueError(text)


class Runtime:
    def __init__(self, root):
        self.root = root; self.scripts = []; self.handlers = {}; self.events = {}
        self.stats = {'state':'complete','filename':'sample.gcode','exception':{},'info':{'current_layer':0}}
        self.hs = {'homed_axes':'xyz','position':[10,20,7,0],'axis_maximum':[271,335,275,0]}
        self.gs = {'gcode_position':[10,20,7,0]}
        self.sd = SimpleNamespace(file_position=0, next_file_position=0, file_path=lambda:str(root/'sample.gcode'),
            is_cmd_from_sd=lambda:True, must_pause_work=False, get_file_position=lambda:self.sd.next_file_position, do_pause=self.stop_dispatch)
        self.pause = SimpleNamespace(is_paused=False)
        self.move = SimpleNamespace(saved_states={}, get_status=lambda now:copy.deepcopy(self.gs))
        self.objects = {'gcode':self, 'print_stats':SimpleNamespace(get_status=lambda now:copy.deepcopy(self.stats)),
            'toolhead':SimpleNamespace(get_status=lambda now:copy.deepcopy(self.hs),wait_moves=lambda:None),
            'gcode_move':self.move,'virtual_sdcard':self.sd,'pause_resume':self.pause,
            'machine_state_manager':SimpleNamespace(get_status=lambda now:{'main_state':1,'action_code':0}),
            'exception_manager':SimpleNamespace(get_status=lambda now:{'exceptions':[]}),
            'purifier':SimpleNamespace(get_status=lambda now:{'power_detected':True}),
            'gcode_macro SET_PRINT_STATS_INFO':SimpleNamespace(variables={})}
        self.handlers = {'SET_PRINT_STATS_INFO':lambda cmd:self.stats['info'].update(current_layer=cmd.get_int('CURRENT_LAYER',0)),
                         'PAUSE':self.pause_original,'RESUME':lambda cmd:self.handlers['RESUME_BASE'](cmd), 'RESUME_BASE':self.resume_original}

    def pause_original(self, cmd):
        self.sd.must_pause_work=True
        self.pause.is_paused=True;self.stats['state']='paused'
        self.move.saved_states['PAUSE_STATE']={'last_position':[1,2,3,4],'absolute_coord':True,'absolute_extrude':False}
    def resume_original(self, cmd): self.pause.is_paused=False;self.stats['state']='printing'
    def stop_dispatch(self):self.sd.must_pause_work=True
    def respond_info(self, text):self.scripts.append('INFO '+text)
    def lookup_object(self, name, default=None): return self.objects.get(name, default)
    def get_reactor(self): return SimpleNamespace(monotonic=lambda:100.)
    def register_event_handler(self, name, callback): self.events[name]=callback
    def register_command(self, name, handler):
        if handler is None: return self.handlers.pop(name,None)
        # Tokenization contract from Klipper gcode.py _process_commands.
        parts = re.split('([A-Z_]+|[A-Z*])', name.upper())
        if ''.join(parts[:3]).strip() != name: raise ValueError('Invalid extended command name: ' + name)
        self.handlers[name]=handler
    def run_script_from_command(self, script):
        self.scripts.append(script)
        if script=='PAUSE': return self.handlers['PAUSE'](Cmd())
        move=re.search(r'G1 Z([0-9.]+)',script)
        if move:
            delta=float(move[1]);self.hs['position'][2]+=delta;self.gs['gcode_position'][2]+=delta


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.source=self.root/'sample.gcode';self.source.write_text(SAMPLE)
        self.runtime=Runtime(self.root)
        config=SimpleNamespace(get_printer=lambda:self.runtime,get=lambda key,default=None:str(self.root/'data') if key=='data_path' else str(self.root) if key=='gcode_root' else default)
        self.module=U1MagnetPause(config);self.module.ready()

    def arm(self,layers=(1,3)):
        token=str(uuid.uuid4());data={'version':1,'createdAt':__import__('time').time(),'token':token,'mode':'next','filename':'sample.gcode','layers':list(layers),**analyse(self.source,layers)}
        save(self.root/'data'/(token+'-prepared.json'),data);self.module.arm(Cmd(TOKEN=token));return data

    def boundary(self,n):
        self.runtime.stats['state']='printing'
        self.runtime.sd.file_position=self.module.plan['markers'].get(str(n),0)
        self.runtime.sd.next_file_position=self.runtime.sd.file_position+50
        self.runtime.handlers['SET_PRINT_STATS_INFO'](Cmd(CURRENT_LAYER=n))
        self.runtime.sd.file_position=self.runtime.sd.next_file_position

    def test_layer_list(self):
        self.assertEqual(parse_layers(' 3, 1  3,2\n'),[1,2,3])
        for text in ('','0','-1','1.5','x','1;PAUSE','nan'):
            with self.subTest(text=text),self.assertRaises(ValueError):parse_layers(text)

    def test_parking_never_moves_up_and_obeys_both_coordinate_limits(self):
        for z,expected in [(7,193),(200,5),(268,2),(270,0.5),(274,0)]:self.assertAlmostEqual(parking_delta(z,z,275),expected)
        self.assertEqual(parking_delta(0,250,275),23)
        with self.assertRaises(ValueError):parking_delta(float('nan'),0,275)

    def test_exact_markers_and_unsupported_file(self):
        plan=analyse(self.source,[2]);offset=plan['markers']['2']
        self.assertTrue(self.source.read_bytes()[offset:].startswith(b'SET_PRINT_STATS_INFO'))
        for raw in ('G1 X1',SAMPLE.replace(';LAYER_CHANGE\n',''),SAMPLE.replace('CURRENT_LAYER=2','CURRENT_LAYER=3'),SAMPLE.replace(';LAYER_CHANGE\n',';LAYER_CHANGE\nG1 E1\n')):
            self.source.write_text(raw)
            with self.assertRaises(ValueError):analyse(self.source,[2])

    def test_arming_does_not_pause_or_move(self):
        self.arm();self.assertEqual(self.module.plan['state'],'armed');self.assertEqual(self.runtime.scripts,[])

    def test_multiple_layers_pause_once_and_stock_resume_returns_control(self):
        self.arm();self.module.new_job();self.boundary(1)
        self.assertTrue(self.runtime.pause.is_paused);self.assertEqual(self.module.plan['done'],[1])
        self.assertAlmostEqual(self.runtime.hs['position'][2],200)
        saved=copy.deepcopy(self.runtime.move.saved_states['PAUSE_STATE'])
        count=len(self.runtime.scripts);self.module.manual(Cmd(CONFIRM=1));self.assertEqual(len(self.runtime.scripts),count)
        self.assertEqual(self.runtime.move.saved_states['PAUSE_STATE'],saved)
        self.runtime.handlers['RESUME'](Cmd());self.assertFalse(self.runtime.pause.is_paused)
        self.boundary(2);self.assertFalse(self.runtime.pause.is_paused)
        self.boundary(3);self.assertTrue(self.runtime.pause.is_paused);self.assertEqual(self.module.plan['done'],[1,3])

    def test_lost_axes_block_all_resume_routes(self):
        self.arm();self.module.new_job();self.boundary(1);self.runtime.hs['homed_axes']='xy'
        for cmd in ('RESUME','RESUME_BASE'):
            with self.assertRaises(ValueError):self.runtime.handlers[cmd](Cmd())
        self.assertTrue(self.runtime.pause.is_paused)

    def test_changed_file_blocks_layer_and_no_lowering(self):
        self.arm();self.module.new_job();self.source.write_text(SAMPLE+';changed')
        self.boundary(1)
        self.assertEqual(self.module.plan['state'],'blocked')
        self.assertTrue(self.runtime.sd.must_pause_work)
        self.assertFalse(any('G1 Z' in s for s in self.runtime.scripts))

    def test_start_other_file_cancels_plan(self):
        self.arm();self.runtime.sd.file_path=lambda:str(self.root/'other.gcode');self.module.new_job()
        self.assertEqual(self.module.plan['state'],'cancelled');self.assertEqual(self.runtime.scripts,[])

    def test_restart_never_rearms(self):
        self.arm();self.module.new_job();self.boundary(1)
        config=SimpleNamespace(get_printer=lambda:self.runtime,get=lambda key,default=None:str(self.root/'data') if key=='data_path' else str(self.root) if key=='gcode_root' else default)
        restarted=U1MagnetPause(config);self.assertEqual(restarted.plan['state'],'needs_review');self.assertIsNone(restarted.park)

    def test_manual_pause_without_plan_and_repeat(self):
        self.runtime.stats['state']='printing';self.runtime.sd.file_position=100;self.runtime.sd.next_file_position=100
        with self.assertRaises(ValueError):self.module.manual(Cmd())
        self.module.manual(Cmd(CONFIRM=1));self.assertTrue(self.runtime.pause.is_paused)
        count=len(self.runtime.scripts);self.module.manual(Cmd(CONFIRM=1));self.assertEqual(len(self.runtime.scripts),count)

    def test_clear_does_not_resume_or_move(self):
        self.arm();self.module.new_job();self.boundary(1);count=len(self.runtime.scripts)
        self.module.clear(Cmd());self.assertTrue(self.runtime.pause.is_paused);self.assertEqual(len(self.runtime.scripts),count)


    def test_command_names_survive_native_tokenization(self):
        for command in MAGNET_COMMANDS.values():
            parts = re.split('([A-Z_]+|[A-Z*])', command + ' CONFIRM=1')
            self.assertEqual(''.join(parts[:3]).strip(), command)
            self.assertIn(command, self.runtime.handlers)
        parts = re.split('([A-Z_]+|[A-Z*])', 'U1_MAGNET_PAUSE CONFIRM=1')
        self.assertEqual(''.join(parts[:3]).strip(), 'U1')
        self.assertEqual(self.module.get_status()['commandVersion'], 2)

    def test_failed_parking_is_not_reported_as_parked_and_cannot_repeat_move(self):
        self.runtime.stats['state']='printing';self.module.manual(Cmd(CONFIRM=1))
        count=len(self.runtime.scripts);self.module.park['state']='blocked'
        self.assertFalse(self.module.get_status()['parked'])
        with self.assertRaises(ValueError):self.module.manual(Cmd(CONFIRM=1))
        self.assertEqual(len(self.runtime.scripts),count)

    def test_native_sd_defers_paused_status_until_layer_handler_returns(self):
        original=self.runtime.pause_original
        def deferred(cmd):
            original(cmd);self.runtime.stats['state']='printing'
        self.module.original_PAUSE=deferred
        self.arm();self.module.new_job();self.boundary(1)
        self.assertEqual(self.module.plan['state'],'waiting_insertion')
        self.assertTrue(self.runtime.pause.is_paused)
        self.assertTrue(self.module.get_status()['parked'])
        self.runtime.stats['state']='paused'
        self.runtime.handlers['RESUME'](Cmd())
        self.boundary(3)
        self.assertEqual(self.module.plan['done'],[1,3])
        self.assertEqual(self.module.plan['state'],'waiting_insertion')

    def test_printing_alone_is_not_a_confirmed_pending_pause(self):
        self.runtime.stats['state']='printing'
        self.runtime.pause.is_paused=True
        with self.assertRaises(ValueError):self.module.lower()
        self.assertFalse(any('G1 Z' in s for s in self.runtime.scripts))

    def test_parking_failure_stops_file_without_raising_sd_cancellation(self):
        self.arm();self.module.new_job()
        def fail():raise ValueError('parking failed')
        self.module.lower=fail
        self.boundary(1)
        self.assertEqual(self.module.plan['state'],'blocked')
        self.assertTrue(self.runtime.pause.is_paused)
        self.assertTrue(self.runtime.sd.must_pause_work)
        self.assertEqual(self.runtime.scripts.count('PAUSE'),1)

if __name__=='__main__':unittest.main()

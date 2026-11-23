"""Real SDL virtual devices exercise polling, mappings and hotplug without hardware."""
import os
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import ctypes as C
from pathlib import Path
from collections import defaultdict
import unittest
import tempfile
import pygame as pg
from gamepads import Gamepads,combine,axis_direction
from game import App,FPS

IDLE=(0,0,False)

class Virtual:
 def __init__(self,sdl,mapped=True):
  self.sdl=sdl
  index=sdl.SDL_JoystickAttachVirtual(1 if mapped else 0,6 if mapped else 2,16 if mapped else 4,1)
  if index<0:raise RuntimeError('SDL virtual joystick attach failed')
  self.handle=sdl.SDL_JoystickOpen(index);self.id=sdl.SDL_JoystickInstanceID(self.handle)
 def axis(self,index,value):
  assert self.sdl.SDL_JoystickSetVirtualAxis(self.handle,index,value)==0
 def button(self,index,value):
  assert self.sdl.SDL_JoystickSetVirtualButton(self.handle,index,int(value))==0
 def hat(self,value):
  assert self.sdl.SDL_JoystickSetVirtualHat(self.handle,0,value)==0
 def detach(self):
  if not self.handle:return
  for i in range(self.sdl.SDL_NumJoysticks()):
   if self.sdl.SDL_JoystickGetDeviceInstanceID(i)==self.id:
    assert self.sdl.SDL_JoystickDetachVirtual(i)==0;break
  self.sdl.SDL_JoystickClose(self.handle);self.handle=None

class GamepadTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  pg.init();pg.display.set_mode((1280,720))
  cls.sdl=C.CDLL(str(Path(pg.__file__).parent/'SDL2.dll'))
  signatures={
   'SDL_JoystickAttachVirtual':([C.c_int]*4,C.c_int),
   'SDL_JoystickOpen':([C.c_int],C.c_void_p),
   'SDL_JoystickInstanceID':([C.c_void_p],C.c_int),
   'SDL_JoystickSetVirtualAxis':([C.c_void_p,C.c_int,C.c_int16],C.c_int),
   'SDL_JoystickSetVirtualButton':([C.c_void_p,C.c_int,C.c_uint8],C.c_int),
   'SDL_JoystickSetVirtualHat':([C.c_void_p,C.c_int,C.c_uint8],C.c_int),
   'SDL_JoystickDetachVirtual':([C.c_int],C.c_int),
   'SDL_JoystickGetDeviceInstanceID':([C.c_int],C.c_int),
   'SDL_JoystickClose':([C.c_void_p],None),
   'SDL_NumJoysticks':([],C.c_int)}
  for name,(args,result) in signatures.items():
   f=getattr(cls.sdl,name);f.argtypes=args;f.restype=result
 @classmethod
 def tearDownClass(cls):pg.quit()
 def setUp(self):
  Path('work').mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir='work')
  self.devices=[];self.pads=Gamepads();self.app=None
  self.assertEqual(pg.joystick.get_count(),0,'Run virtual tests without physical pads connected')
 def tearDown(self):
  self.pads.close()
  for v in reversed(self.devices):v.detach()
  pg.event.pump();pg.event.clear()
  if self.app:pg.mixer.stop()
  self.temp.cleanup()
 def add(self,mapped=True):
  v=Virtual(self.sdl,mapped);self.devices.append(v);self.events();return v
 def events(self):
  for event in pg.event.get():
   if self.app:self.app.pad_event(event)
   else:self.pads.event(event)
 def poll(self):pg.event.pump();return self.pads.poll()
 def application(self):
  self.pads.close();self.app=App(windowed=True,settings_path=Path(self.temp.name)/'settings.json');self.pads=self.app.pads;return self.app
 def command(self):
  pg.event.pump();return self.app.gamepad_commands(defaultdict(bool))
 def test_no_pads_preserves_all_keyboard_inputs(self):
  keyboard=[(1,0,True),(0,-1,False),(-1,1,True),IDLE]
  self.assertEqual(combine(keyboard,self.poll()),keyboard)
 def test_four_devices_have_four_independent_stable_player_slots(self):
  vs=[self.add() for _ in range(4)]
  self.assertEqual([p.id for p in self.pads.slots],[v.id for v in vs])
  vs[0].axis(0,32767);vs[1].axis(1,-32768);vs[2].axis(0,-32768);vs[3].button(0,1)
  self.assertEqual(self.poll(),[(1,0,False),(0,-1,False),(-1,0,False),(0,0,True)])
 def test_all_analog_directions_and_diagonals(self):
  v=self.add()
  for x in (-1,0,1):
   for y in (-1,0,1):
    v.axis(0,x*30000);v.axis(1,y*30000)
    self.assertEqual(self.poll()[0],(x,y,False))
 def test_analog_deadzone_and_hysteresis_prevent_drift(self):
  v=self.add();v.axis(0,10000);self.assertEqual(self.poll()[0][0],0)
  v.axis(0,20000);self.assertEqual(self.poll()[0][0],1)
  v.axis(0,10000);self.assertEqual(self.poll()[0][0],1)
  v.axis(0,7000);self.assertEqual(self.poll()[0][0],0)
  self.assertEqual(axis_direction(-.3,-1),-1);self.assertEqual(axis_direction(-.2,-1),0)
 def test_mapped_dpad_has_priority_over_stick(self):
  v=self.add();v.axis(0,-30000);v.button(pg.CONTROLLER_BUTTON_DPAD_UP,1)
  self.assertEqual(self.poll()[0],(0,-1,False))
  v.button(pg.CONTROLLER_BUTTON_DPAD_RIGHT,1);self.assertEqual(self.poll()[0],(1,-1,False))
 def test_every_face_button_can_be_fire(self):
  v=self.add()
  for button in range(4):
   v.button(button,1);self.assertTrue(self.poll()[0][2])
   v.button(button,0);self.assertFalse(self.poll()[0][2])
 def test_raw_usb_joystick_fallback_axes_hat_and_fire(self):
  v=self.add(mapped=False);self.assertIsNone(self.pads.slots[0].controller)
  v.axis(0,-30000);self.assertEqual(self.poll()[0],(-1,0,False))
  v.hat(3);v.button(0,1);self.assertEqual(self.poll()[0],(1,-1,True))
 def test_keyboard_and_pad_combine_without_cancelling_keyboard(self):
  v=self.add();v.axis(0,30000);v.button(0,1)
  self.assertEqual(combine([(-1,0,False),IDLE,IDLE,IDLE],self.poll())[0],(-1,0,True))
  self.assertEqual(combine([(0,-1,False),IDLE,IDLE,IDLE],self.poll())[0],(1,-1,True))
 def test_disconnect_clears_input_without_renumbering_other_players(self):
  vs=[self.add() for _ in range(4)];vs[0].button(0,1);self.assertTrue(self.poll()[0][2])
  vs[0].detach();self.events()
  self.assertIsNone(self.pads.slots[0]);self.assertEqual([p.id for p in self.pads.slots[1:]],[v.id for v in vs[1:]])
  self.assertEqual(self.poll()[0],IDLE)
 def test_reconnect_fills_free_slot_without_moving_other_pads(self):
  v0=self.add();v1=self.add();v0.detach();self.events();new=self.add()
  self.assertEqual(self.pads.slots[0].id,new.id);self.assertEqual(self.pads.slots[1].id,v1.id)
 def test_fifth_pad_does_not_control_an_already_assigned_player(self):
  vs=[self.add() for _ in range(5)];vs[4].button(0,1)
  self.assertEqual(self.poll(),[IDLE]*4)
  vs[1].detach();self.events();self.assertEqual(self.pads.slots[1].id,vs[4].id)
  self.assertTrue(self.poll()[1][2])
 def test_duplicate_add_events_do_not_duplicate_controller(self):
  v=self.add();self.pads.scan();self.pads.scan()
  self.assertEqual([p.id for p in self.pads.slots if p],[v.id])
 def test_start_and_fire_edges_do_not_repeat_while_held(self):
  v=self.add();v.button(0,1);v.button(pg.CONTROLLER_BUTTON_START,1);self.poll()
  self.assertTrue(self.pads.fire_pressed);self.assertTrue(self.pads.start_pressed)
  self.poll();self.assertFalse(self.pads.fire_pressed);self.assertFalse(self.pads.start_pressed)
 def test_start_game_and_pause_resume_from_pad(self):
  v=self.add();app=self.application();v.button(0,1);self.command();self.assertEqual(app.state,'fight')
  v.button(0,0);v.button(pg.CONTROLLER_BUTTON_START,1);self.command();self.assertTrue(app.paused)
  self.command();self.assertTrue(app.paused)
  v.button(pg.CONTROLLER_BUTTON_START,0);self.command()
  v.button(pg.CONTROLLER_BUTTON_START,1);self.command();self.assertFalse(app.paused)
 def test_unplug_during_fight_pauses_and_keyboard_remains_available(self):
  v=self.add();app=self.application();app.reset();v.detach();self.events();self.assertTrue(app.paused)
  keys=defaultdict(bool,{pg.K_RIGHT:True,pg.K_LCTRL:True})
  self.assertEqual(app.gamepad_commands(keys)[0],(1,0,True))
 def test_pad_fire_up_repeats_real_game_jumps_and_release_stops(self):
  v=self.add();app=self.application();app.reset();f=app.arena.fighters[0]
  v.axis(1,-30000);v.button(0,1);loops=0;last=0
  for _ in range(180):
   app.arena.step(1/FPS,self.command())
   if f.time<last:loops+=1
   last=f.time
  self.assertGreaterEqual(loops,4)
  v.axis(1,0);v.button(0,0)
  for _ in range(100):app.arena.step(1/FPS,self.command())
  self.assertEqual(f.move,'idle')
 def test_four_raw_devices_also_keep_their_own_player(self):
  vs=[self.add(mapped=False) for _ in range(4)]
  for i,v in enumerate(vs):
   v.button(0,1);cmd=self.poll();self.assertTrue(cmd[i][2]);self.assertEqual(sum(c[2] for c in cmd),1);v.button(0,0)
 def test_each_pad_selects_its_own_character_once_per_direction_press(self):
  vs=[self.add() for _ in range(4)];app=self.application()
  for i,v in enumerate(vs):
   v.axis(0,30000);self.command();self.assertEqual(app.skins[i],'ryu')
   self.command();self.assertEqual(app.skins[i],'ryu')
   v.axis(0,0);self.command()
  self.assertEqual(app.skins,['ryu']*4)
  vs[0].button(0,1);self.command();self.assertEqual(app.state,'fight')
  vs[0].axis(0,-30000);self.command();self.assertEqual(app.skins,['ryu']*4)

if __name__=='__main__':unittest.main(verbosity=2)

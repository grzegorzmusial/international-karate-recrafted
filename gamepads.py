"""Optional four-pad input with stable player slots and keyboard fallback."""
import pygame as pg
try:
 from pygame._sdl2 import controller as sdl_controller
except ImportError:
 sdl_controller=None

NEUTRAL=(0,0,False)

def axis_direction(value,previous=0):
 """Separate engage/release thresholds avoid drift and diagonal chatter."""
 if value>=.40:return 1
 if value<=-.40:return -1
 if previous==1 and value>.25:return 1
 if previous==-1 and value<-.25:return -1
 return 0

def combine(keyboard,pads):
 """Keyboard directions take priority per axis; either device may hold Fire."""
 return [(kx or px,ky or py,bool(kf or pf))
         for (kx,ky,kf),(px,py,pf) in zip(keyboard,pads)]

class Pad:
 def __init__(self,joystick,controller=None):
  self.joystick=joystick;self.controller=controller
  self.id=joystick.get_instance_id();self.name=joystick.get_name()
  self.axes=[0,0];self.previous_fire=False;self.previous_start=False
 def read(self):
  j=self.joystick;c=self.controller
  if c:
   if not c.attached():raise pg.error('Controller disconnected')
   x=c.get_axis(pg.CONTROLLER_AXIS_LEFTX)/32768
   y=c.get_axis(pg.CONTROLLER_AXIS_LEFTY)/32768
   up=c.get_button(pg.CONTROLLER_BUTTON_DPAD_UP);down=c.get_button(pg.CONTROLLER_BUTTON_DPAD_DOWN)
   left=c.get_button(pg.CONTROLLER_BUTTON_DPAD_LEFT);right=c.get_button(pg.CONTROLLER_BUTTON_DPAD_RIGHT)
   dpad=bool(up or down or left or right)
   hat=(int(right)-int(left),int(down)-int(up))
   fire=any(c.get_button(b) for b in (pg.CONTROLLER_BUTTON_A,pg.CONTROLLER_BUTTON_B,pg.CONTROLLER_BUTTON_X,pg.CONTROLLER_BUTTON_Y))
   start=bool(c.get_button(pg.CONTROLLER_BUTTON_START))
  else:
   x=j.get_axis(0) if j.get_numaxes()>0 else 0
   y=j.get_axis(1) if j.get_numaxes()>1 else 0
   h=j.get_hat(0) if j.get_numhats()>0 else (0,0)
   hat=(h[0],-h[1]);dpad=hat!=(0,0)
   fire=any(j.get_button(b) for b in range(min(4,j.get_numbuttons())))
   start=bool(j.get_button(7)) if j.get_numbuttons()>7 else False
  self.axes=[axis_direction(x,self.axes[0]),axis_direction(y,self.axes[1])]
  dx,dy=hat if dpad else self.axes
  fire_edge=bool(fire and not self.previous_fire);start_edge=bool(start and not self.previous_start)
  self.previous_fire=bool(fire);self.previous_start=start
  return (dx,dy,bool(fire)),fire_edge,start_edge
 def close(self):
  if self.controller:
   try:self.controller.quit()
   except pg.error:pass
  try:self.joystick.quit()
  except pg.error:pass

class Gamepads:
 def __init__(self):
  pg.joystick.init()
  if sdl_controller:sdl_controller.init()
  self.slots=[None]*4;self.fire_pressed=False;self.start_pressed=False;self.lost=False
  self.scan()
 def scan(self):
  known={p.id for p in self.slots if p}
  for index in range(pg.joystick.get_count()):
   if all(self.slots):break
   try:
    joystick=pg.joystick.Joystick(index)
    if joystick.get_instance_id() in known:continue
    controller=None
    if sdl_controller and sdl_controller.is_controller(index):
     try:controller=sdl_controller.Controller.from_joystick(joystick)
     except pg.error:pass
    pad=Pad(joystick,controller);self.slots[self.slots.index(None)]=pad;known.add(pad.id)
   except pg.error:continue
 def remove(self,instance_id):
  for i,pad in enumerate(self.slots):
   if pad and pad.id==instance_id:
    pad.close();self.slots[i]=None;return True
  return False
 def event(self,event):
  if event.type==pg.JOYDEVICEADDED:self.scan()
  elif event.type==pg.JOYDEVICEREMOVED:
   removed=self.remove(event.instance_id);self.scan();return removed
  return False
 def poll(self):
  self.fire_pressed=False;self.start_pressed=False;self.lost=False;commands=[]
  for pad in list(self.slots):
   if pad is None:commands.append(NEUTRAL);continue
   try:
    command,fire,start=pad.read();commands.append(command)
    self.fire_pressed|=fire;self.start_pressed|=start
   except pg.error:
    self.remove(pad.id);commands.append(NEUTRAL);self.lost=True
  return commands
 def close(self):
  for pad in self.slots:
   if pad:pad.close()
  self.slots=[None]*4

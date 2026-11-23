"""Four-player local free-for-all. Native Atari animation/PCM assets; custom combat."""
import os,sys,json,math
from pathlib import Path
from dataclasses import dataclass,field
import pygame as pg
from gamepads import Gamepads,combine
from characters import Characters,SKINS,SKIN_NAMES,RENDER_SCALE
from arena_background import ArenaBackground
ROOT=Path(__file__).resolve().parent
W,H,FLOOR=1280,720,570
FPS=49.860759735
COLORS=[(232,225,216),(207,72,75),(67,185,122),(74,144,235)]
LABELS=['STRZAŁKI + CTRL','WASD + SPACJA','IJKL + U','TFGH + E']
KEYS=[(pg.K_UP,pg.K_DOWN,pg.K_LEFT,pg.K_RIGHT,pg.K_LCTRL),(pg.K_w,pg.K_s,pg.K_a,pg.K_d,pg.K_SPACE),(pg.K_i,pg.K_k,pg.K_j,pg.K_l,pg.K_u),(pg.K_t,pg.K_g,pg.K_f,pg.K_h,pg.K_e)]
NO_FIRE={(0,-1):'jump',(1,-1):'punch',(1,0):'walk',(1,1):'chest',(0,1):'sweep',(-1,1):'crouch',(-1,0):'backwalk',(-1,-1):'backpunch'}
FIRE={(0,-1):'jumpkick',(1,-1):'flip',(1,0):'high',(1,1):'shin',(0,1):'backcrouch',(-1,1):'backshin',(-1,0):'reverse',(-1,-1):'backflip'}
# Windows follow the native measured contact phases. Collision additionally requires opaque sprite overlap.
ATTACKS={'punch':(.22,.46,'mid'),'chest':(.25,.51,'mid'),'sweep':(.22,.51,'low'),'crouch':(.22,.48,'mid'),'backpunch':(.25,.51,'high'),'jumpkick':(.25,.55,'high'),'high':(.25,.51,'high'),'shin':(.22,.51,'low'),'backcrouch':(.22,.51,'mid'),'backshin':(.25,.53,'low'),'reverse':(.42,.72,'mid')}
BACK={'backpunch','backcrouch','backshin'}
AIRBORNE={'jump','jumpkick','flip','backflip'}
FONT={}
def text(s,v,size,x,y,color=(242,233,214),center=False):
 if size not in FONT:FONT[size]=pg.font.SysFont('Segoe UI',size,bold=size>=24)
 im=FONT[size].render(str(v),True,color);r=im.get_rect();r.center=(x,y) if center else r.center
 if not center:r.topleft=(x,y)
 s.blit(im,r)
def inputs(keys):
 result=[]
 for i,(up,down,left,right,fire) in enumerate(KEYS):
  result.append((int(bool(keys[right]))-int(bool(keys[left])),int(bool(keys[down]))-int(bool(keys[up])),bool(keys[fire]) or (i==0 and bool(keys[pg.K_RCTRL]))))
 return result
@dataclass
class Fighter:
 id:int
 x:float
 face:int
 move:str='idle'
 time:float=0
 facing:int=1
 score:int=0
 received:int=0
 invuln:float=0
 walktime:float=0
 victims:set=field(default_factory=set)
 last_command:tuple=(0,0,False)
 reaction:str='fall'
 motion_origin:float=0

class Sprites:
 def __init__(self):
  self.data=json.loads((ROOT/'assets/moves.json').read_text())['moves'];self.cache={}
 def record(self,f):
  seq=self.data[f.reaction if f.move=='fall' else f.move];idx=min(int(f.time*FPS),len(seq)-1)
  if f.move in ('walk','backwalk','idle'):idx=int(f.walktime*FPS)%len(seq)
  item=seq[idx];face=f.facing if f.move not in ('idle','walk','backwalk') else f.face
  return item,face
 def frame(self,f):
  item,face=self.record(f)
  key=(item['image'],f.id,face)
  if key not in self.cache:
   raw=pg.image.load(str(ROOT/'assets/frames'/f"{item['image']}.png")).convert_alpha()
   colored=pg.Surface(raw.get_size(),pg.SRCALPHA)
   for x in range(raw.get_width()):
    for y in range(raw.get_height()):
     c=raw.get_at((x,y))
     if c.a and c[:3]==(213,210,213):raw.set_at((x,y),COLORS[f.id])
     if c.a and c[:3]!=(0,4,0):colored.set_at((x,y),(255,255,255,255))
   # Retain EVERY component containing body/skin, including separate hands and feet.
   # A detached black floor shadow stays visible but cannot receive an attack.
   seeds=pg.mask.from_surface(colored);combat=raw.copy()
   for component in pg.mask.from_surface(raw).connected_components():
    if component.overlap(seeds,(0,0)) is None:
     for box in component.get_bounding_rects():
      for x in range(box.left,box.right):
       for y in range(box.top,box.bottom):
        if component.get_at((x,y)):combat.set_at((x,y),(0,0,0,0))
   im=pg.transform.scale2x(pg.transform.scale2x(raw))
   combat=pg.transform.scale2x(pg.transform.scale2x(combat))
   if face<0:im=pg.transform.flip(im,True,False);combat=pg.transform.flip(combat,True,False)
   self.cache[key]=(im,pg.mask.from_surface(combat))
  im,mask=self.cache[key];dx,dy=item['offset'];dx*=4;dy*=4
  if face<0:dx=-dx-im.get_width()
  # Airborne offsets are local to the moving fighter; travel advances its world position.
  rect=im.get_rect(topleft=(round(f.x+dx),round(FLOOR+dy)))
  return im,mask,rect
 def duration(self,move):return len(self.data[move])/FPS
 def advance_motion(self,f):
  if f.move not in AIRBORNE:return
  seq=self.data[f.move];item=seq[min(int(f.time*FPS),len(seq)-1)]
  desired=f.motion_origin+item['travel']*4*f.facing
  im,_,rect=self.frame(f);dx=rect.x-round(f.x)
  # Keep the complete current pose visible at either arena edge.
  low=max(105,8-dx);high=min(1175,W-8-dx-im.get_width())
  f.x=max(low,min(high,desired))

class Audio:
 def __init__(self):
  self.enabled=True;self.music=True;self.sounds={}
  try:
   from pygame._sdl2.audio import get_audio_device_names
   dev=next((d for d in get_audio_device_names(False) if 'SMSL' in d.upper()),None)
   pg.mixer.quit();pg.mixer.init(44100,-16,2,512,devicename=dev)
   pg.mixer.set_num_channels(16)
   self.sounds={n:pg.mixer.Sound(str(ROOT/'assets'/f'{n}.wav')) for n in ('music','hit','move')}
   self.sounds['music'].set_volume(.42);self.sounds['hit'].set_volume(.8);self.sounds['move'].set_volume(.65)
   self.channel=pg.mixer.Channel(0);self.channel.play(self.sounds['music'],-1)
  except pg.error:pass
 def play(self,n):
  if self.enabled and n in self.sounds:
   channel=pg.mixer.find_channel()
   if channel:channel.play(self.sounds[n])
 def sync(self):
  if self.sounds:
   self.channel.set_volume(1 if self.enabled and self.music else 0)

class Arena:
 def __init__(self,sprites,audio=None):
  self.sprites=sprites;self.audio=audio;self.elapsed=0
  self.fighters=[Fighter(i,x,1 if i<2 else -1) for i,x in enumerate((170,470,810,1110))]
 def step(self,dt,commands):
  self.elapsed+=dt
  for f,(dx,dy,fire) in zip(self.fighters,commands):
   command=(dx,dy,fire)
   completed=None
   f.invuln=max(0,f.invuln-dt);f.time+=dt;f.walktime+=dt
   action=(FIRE if fire else NO_FIRE).get((dx*f.face,dy),'idle')
   busy=f.move not in ('idle','walk','backwalk')
   if busy:self.sprites.advance_motion(f)
   if busy and f.time>=self.sprites.duration(f.reaction if f.move=='fall' else f.move):
    completed=f.move
    if f.move in BACK:
     f.face=-f.facing
     action=(FIRE if fire else NO_FIRE).get((dx*f.face,dy),'idle')
    f.move='idle';f.time=0;busy=False
   if busy:
    f.last_command=command;continue
   if action in ('walk','backwalk'):
    # Directions remain physical joystick directions; walking backwards preserves facing.
    delta=dx*155*dt
    nextx=max(105,min(1175,f.x+delta))
    f.x=nextx
    f.move=action
   elif action!='idle':
    # Held Fire + up, including diagonals, repeats only after the previous landing.
    if command!=f.last_command or action in ('jumpkick','flip','backflip'):
     # Reuse the completed landing as the next flip's preparation (native 40-frame rhythm).
     loop=completed==action and command==f.last_command and action in ('flip','backflip')
     f.move=action;f.time=4/FPS if loop else 0;f.facing=f.face;f.motion_origin=f.x;f.victims.clear()
     self.sprites.advance_motion(f)
     if self.audio and action in ATTACKS:self.audio.play('move')
    else:f.move='idle'
   else:f.move='idle'
   f.last_command=command
  # Resolve all contacts before applying reactions so simultaneous attacks are fair.
  contacts=[]
  for attacker in self.fighters:
   if attacker.move not in ATTACKS:continue
   begin,end,level=ATTACKS[attacker.move]
   if not begin<=attacker.time<=end:continue
   _,am,ar=self.sprites.frame(attacker)
   direction=attacker.facing*(-1 if attacker.move in BACK else 1)
   y0,y1={'high':(FLOOR-230,FLOOR-85),'mid':(FLOOR-145,FLOOR-35),'low':(FLOOR-55,FLOOR+5)}[level]
   xr=ar.right if direction>0 else ar.left
   x0,x1=sorted((round(attacker.x+direction*26),xr))
   strike=pg.Rect(x0,y0,max(1,x1-x0),y1-y0)
   # Restrict contact to the actual attack limb pixels in this frame.
   clip=strike.clip(ar)
   if clip.width==0 or clip.height==0:continue
   limb=pg.mask.Mask(ar.size)
   local=clip.move(-ar.x,-ar.y)
   limb.draw(am,(0,0));region=pg.mask.Mask(ar.size);region.draw(pg.mask.Mask(local.size,fill=True),local.topleft)
   limb=limb.overlap_mask(region,(0,0))
   for victim in self.fighters:
    if victim.id==attacker.id or victim.id in attacker.victims or victim.move=='fall' or victim.invuln>0:continue
    _,vm,vr=self.sprites.frame(victim)
    if limb.overlap(vm,(vr.x-ar.x,vr.y-ar.y)) is not None:
     contacts.append((attacker.id,victim.id))
  for aid,vid in contacts:
   a=self.fighters[aid];v=self.fighters[vid]
   a.victims.add(vid);a.score+=1;v.received+=1
  reactions={}
  for aid,vid in contacts:
   a=self.fighters[aid]
   direction=a.facing*(-1 if a.move in BACK else 1)
   reaction='fall_low' if ATTACKS[a.move][2]=='low' else 'fall'
   if vid not in reactions or reaction=='fall':reactions[vid]=(reaction,-direction)
  for vid,(reaction,facing) in reactions.items():
   v=self.fighters[vid];v.move='fall';v.reaction=reaction;v.time=0;v.facing=facing
   v.invuln=self.sprites.duration(reaction)+.65
   if self.audio:self.audio.play('hit')
  return contacts

class App:
 def __init__(self,windowed=False,settings_path=None):
  pg.init();self.fullscreen=not windowed
  self.screen=pg.display.set_mode((0,0),pg.FULLSCREEN) if self.fullscreen else pg.display.set_mode((W,H),pg.RESIZABLE)
  pg.display.set_caption('International Karate • HD • Recrafted 6.1')
  self.canvas=pg.Surface((W,H))
  self.background=ArenaBackground(ROOT/'assets',(W*RENDER_SCALE,H*RENDER_SCALE))
  self.render_canvas=pg.Surface((W*RENDER_SCALE,H*RENDER_SCALE));self.overlay=pg.Surface((W,H),pg.SRCALPHA)
  self.characters=Characters(ROOT);self.skins=['original']*4;self.menu_directions=[0]*4
  self.settings_path=Path(settings_path) if settings_path else (Path(sys.executable).parent if getattr(sys,'frozen',False) else ROOT)/'settings.json'
  try:
   saved=json.loads(self.settings_path.read_text(encoding='utf8')).get('skins')
   if isinstance(saved,list) and len(saved)==4 and all(s in SKINS for s in saved):self.skins=saved
  except (OSError,ValueError,AttributeError):pass
  self.sprites=Sprites();self.audio=Audio();self.arena=Arena(self.sprites,self.audio);self.pads=Gamepads()
  self.state='menu';self.paused=False;self.help=False;self.clock=pg.time.Clock()
 def reset(self):
  self.characters.warm(self.skins)
  self.arena=Arena(self.sprites,self.audio);self.state='fight';self.paused=False
 def key(self,key):
  if key==pg.K_F11:
   self.fullscreen=not self.fullscreen;self.screen=pg.display.set_mode((0,0),pg.FULLSCREEN) if self.fullscreen else pg.display.set_mode((W,H),pg.RESIZABLE)
  elif key==pg.K_F1:self.help=not self.help
  elif key==pg.K_m:self.audio.enabled=not self.audio.enabled;self.audio.sync()
  elif key==pg.K_n:self.audio.music=not self.audio.music;self.audio.sync()
  elif key==pg.K_F2 and self.state=='menu' and not self.help:
   self.skins=['ryu','ken','ryu','ken'] if self.skins==['original']*4 else ['original']*4
   self.save_skins()
  elif key==pg.K_ESCAPE:
   if self.help:self.help=False
   elif self.state=='menu':return False
   elif self.paused:self.state='menu';self.paused=False
   else:self.paused=True
  elif self.state=='menu':
   if key==pg.K_RETURN:self.reset()
   elif not self.help:
    for player,(_,_,left,right,_) in enumerate(KEYS):
     if key in (left,right):self.choose_skin(player,1 if key==right else -1)
  elif self.state=='fight' and key in (pg.K_p,pg.K_RETURN):self.paused=not self.paused
  return True
 def choose_skin(self,player,delta):
  self.skins[player]=SKINS[(SKINS.index(self.skins[player])+delta)%len(SKINS)]
  self.save_skins()
 def save_skins(self):
  try:self.settings_path.write_text(json.dumps({'skins':self.skins}),encoding='utf8')
  except OSError:pass
 def draw(self):
  s=self.canvas
  pg.draw.rect(s,(9,22,35),(0,0,W,112))
  for f in self.arena.fighters:
   x=24+f.id*316
   pg.draw.rect(s,COLORS[f.id],(x,18,4,67))
   text(s,f'P{f.id+1} {SKIN_NAMES[SKINS.index(self.skins[f.id])]}  {f.score}',19,x+15,16,COLORS[f.id]);text(s,f'{LABELS[f.id]} / PAD {f.id+1}',12,x+15,55)
   pad=self.pads.slots[f.id]
   text(s,pad.name[:31] if pad else 'PAD NIEPODŁĄCZONY',10,x+15,76,COLORS[f.id] if pad else (150,168,181))
   text(s,f'OTRZYMANE: {f.received}',10,x+15,94,(150,168,181))
  order=sorted(self.arena.fighters,key=lambda f:(2 if f.move in AIRBORNE else 0 if f.move=='fall' else 1,f.id))
  k=RENDER_SCALE
  self.background.draw(self.render_canvas,pg.time.get_ticks()/1000)
  self.render_canvas.blit(pg.transform.smoothscale(s.subsurface((0,0,W,112)),(W*k,112*k)),(0,0))
  shadow=pg.Surface((116*k,14*k),pg.SRCALPHA)
  pg.draw.ellipse(shadow,(8,15,24,100),shadow.get_rect())
  for f in order:self.render_canvas.blit(shadow,(round((f.x-58)*k),(FLOOR-4)*k))
  for f in order:
   im,r=self.characters.frame(f,self.sprites,self.skins[f.id]);self.render_canvas.blit(im,r)
   x=min((W-22)*k,max(22*k,r.centerx));y=max(130*k,r.top-20*k)
   pg.draw.circle(self.render_canvas,(10,23,36),(x,y),14*k)
   pg.draw.circle(self.render_canvas,COLORS[f.id],(x,y),14*k,2*k)
   text(self.render_canvas,str(f.id+1),16*k,x,y,COLORS[f.id],True)
  self.overlay.fill((0,0,0,0));s=self.overlay
  pg.draw.rect(s,(9,22,35),(0,672,W,48))
  minutes=int(self.arena.elapsed)//60;seconds=int(self.arena.elapsed)%60
  text(s,f'WALKA BEZ KOŃCA  •  {minutes:02}:{seconds:02}  •  KAŻDY NA KAŻDEGO',14,25,685)
  text(s,'P PAUZA   F1 CIOSY   M DŹWIĘK   N MUZYKA   F11 EKRAN',12,836,687)
  if self.state=='menu' or self.paused or self.help:
   shade=pg.Surface((W,H),pg.SRCALPHA);shade.fill((6,17,29,220));s.blit(shade,(0,0))
   if self.help:self.draw_help(s)
   elif self.state=='menu':
    text(s,'INTERNATIONAL KARATE',48,640,161,center=True)
    text(s,'CZTERECH GRACZY',34,640,224,(234,183,106),True)
    text(s,'WYBIERZ POSTAĆ DLA KAŻDEGO GRACZA',18,640,280,center=True)
    for i,label in enumerate(LABELS):
     y=329+i*51
     text(s,f'GRACZ {i+1}   ‹  {SKIN_NAMES[SKINS.index(self.skins[i])]}  ›',23,640,y,COLORS[i],True)
     text(s,label+f' / PAD {i+1}',11,640,y+23,center=True)
    text(s,'← →   A / D   J / L   F / H   lub lewo / prawo na swoim padzie',13,640,541,center=True)
    text(s,'F2: ORYGINALNI / RYU I KEN',16,640,571,(234,183,106),True)
    text(s,'ENTER / FIRE NA PADZIE — ROZPOCZNIJ',24,640,613,(234,183,106),True)
    text(s,f'PADY: {sum(p is not None for p in self.pads.slots)}/4    F1 CIOSY    F11 EKRAN    ESC WYJŚCIE',12,640,655,center=True)
   else:
    text(s,'PAUZA',52,640,308,center=True)
    text(s,'P / ENTER / START NA PADZIE — WRÓĆ     ESC — MENU',18,640,382,center=True)
  if self.state=='menu' or self.paused or self.help:
   self.render_canvas.blit(pg.transform.smoothscale(s,(W*k,H*k)),(0,0))
  else:self.render_canvas.blit(pg.transform.smoothscale(s.subsurface((0,672,W,48)),(W*k,48*k)),(0,672*k))
  self.present()
 def draw_help(self,target=None):
  s=target if target is not None else self.canvas;s.fill((9,22,35));text(s,'MAPA CIOSÓW',34,640,52,(234,183,106),True)
  text(s,'Względem kierunku patrzenia. FIRE: Ctrl / spacja / U / E lub A / × na padzie.',16,640,105,center=True)
  left=['↑  skok','↑ + przód  wypad z ciosem','przód  krok w przód','↓ + przód  kopnięcie w tułów','↓  podcięcie','↓ + tył  cios w przysiadzie','tył  krok w tył','↑ + tył  wypad i obrót']
  right=['↑  kopnięcie w locie','↑ + przód  salto w przód','przód  kopnięcie wysokie','↓ + przód  niskie kopnięcie','↓  cios w tył w przysiadzie','↓ + tył  niskie kopnięcie w tył','tył  kopnięcie z obrotem','↑ + tył  salto w tył']
  text(s,'BEZ FIRE',24,90,160);text(s,'Z FIRE',24,685,160)
  for i,(a,b) in enumerate(zip(left,right)):text(s,a,19,90,218+43*i);text(s,b,19,685,218+43*i)
  text(s,'Trzymaj Fire + góra lub góra po skosie, aby powtarzać skoki. F1 / ESC — wróć.',17,640,640,center=True)
 def present(self):
  w,h=self.screen.get_size();scale=min(w/W,h/H);size=(round(W*scale),round(H*scale));self.screen.fill((0,0,0))
  frame=self.render_canvas if size==self.render_canvas.get_size() else pg.transform.smoothscale(self.render_canvas,size)
  self.screen.blit(frame,((w-size[0])//2,(h-size[1])//2));pg.display.flip()
 def menu_click(self,pos):
  w,h=self.screen.get_size();scale=min(w/W,h/H)
  x=(pos[0]-(w-W*scale)/2)/scale;y=(pos[1]-(h-H*scale)/2)/scale
  if 350<=x<=930 and 308<=y<512:
   self.choose_skin(min(3,int((y-308)//51)),-1 if x<640 else 1)
  elif 350<=x<=930 and 588<=y<=636:self.reset()
 def pad_event(self,event):
  if self.pads.event(event) and self.state=='fight':self.paused=True
 def gamepad_commands(self,keys):
  pad_commands=self.pads.poll()
  if self.pads.lost and self.state=='fight':self.paused=True
  for i,(dx,_,_) in enumerate(pad_commands):
   if self.state=='menu' and not self.help and dx and dx!=self.menu_directions[i]:self.choose_skin(i,dx)
   self.menu_directions[i]=dx
  if self.pads.start_pressed or (self.state=='menu' and self.pads.fire_pressed):
   if self.help:self.help=False
   else:self.key(pg.K_RETURN)
  return combine(inputs(keys),pad_commands)
 def run(self):
  running=True;acc=0
  while running:
   acc+=min(.1,self.clock.tick(60)/1000)
   for e in pg.event.get():
    self.pad_event(e)
    if e.type==pg.QUIT:running=False
    elif e.type==pg.KEYDOWN:running=self.key(e.key)
    elif e.type==pg.WINDOWFOCUSLOST and self.state=='fight':self.paused=True
    elif e.type==pg.MOUSEBUTTONDOWN and self.state=='menu' and not self.help:self.menu_click(e.pos)
   command=self.gamepad_commands(pg.key.get_pressed())
   while acc>=1/FPS:
    if self.state=='fight' and not self.paused and not self.help:self.arena.step(1/FPS,command)
    acc-=1/FPS
   self.draw()
  self.pads.close();pg.quit()
if __name__=='__main__':
 try:App('--windowed' in sys.argv).run()
 except Exception:
  import traceback
  target=Path(sys.executable).parent if getattr(sys,'frozen',False) else ROOT
  (target/'error.log').write_text(traceback.format_exc(),encoding='utf8');raise

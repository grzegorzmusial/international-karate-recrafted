"""HD presentation only. Native animation timing and combat masks stay in game.py."""
from pathlib import Path
from collections import OrderedDict
import json
import numpy as np
import pygame as pg

SKINS=('original','ryu','ken','atari')
SKIN_NAMES=('ORYGINALNY HD','RYU HD','KEN HD','ORYGINALNY ATARI')
RENDER_SCALE=2
COLORS=((232,225,216),(207,72,75),(67,185,122),(74,144,235))

class Characters:
 def __init__(self,root):
  self.root=Path(root)/'assets/hd'
  poses=json.loads((self.root/'poses.json').read_text())
  self.poses={p['image']:{**p,'part':i//12+1,'cell':i%12} for i,p in enumerate(poses)}
  self.aliases=json.loads((self.root/'aliases.json').read_text())
  self.atlases={};self.base={};self.frames=OrderedDict()
 def source(self,theme,key):
  cachekey=(theme,key)
  if cachekey not in self.base:
   if key in self.aliases:
    alias=self.aliases[key];image=self.source(theme,alias['image'])
    self.base[cachekey]=pg.transform.flip(image,True,False) if alias['mirror'] else image
    return self.base[cachekey]
   meta=self.poses[key];atlas_key=(theme,meta['part'])
   if atlas_key not in self.atlases:
    self.atlases[atlas_key]=pg.image.load(str(self.root/f'{theme}-{meta["part"]}.png')).convert_alpha()
   atlas=self.atlases[atlas_key];col=meta['cell']%4;row=meta['cell']//4
   x0=round(col*atlas.get_width()/4);x1=round((col+1)*atlas.get_width()/4)
   y0=round(row*atlas.get_height()/3);y1=round((row+1)*atlas.get_height()/3)
   cell=atlas.subsurface((x0,y0,x1-x0,y1-y0)).copy()
   bounds=cell.get_bounding_rect(min_alpha=96)
   if bounds.width<16 or bounds.height<16:raise ValueError(f'Brak pozy HD: {theme} {meta["part"]}:{meta["cell"]}')
   image=cell.subsurface(bounds).copy()
   # Normalize nearly transparent export padding, preserving antialiased edges.
   alpha=pg.surfarray.pixels_alpha(image);alpha[alpha<32]=0;del alpha
   self.base[cachekey]=image
  return self.base[cachekey]
 def tint(self,image,player,theme):
  result=image.copy()
  if theme!='original' or player==0:return result
  rgb=pg.surfarray.pixels3d(result);values=rgb.astype(np.float32)
  high=values.max(axis=2);low=values.min(axis=2)
  saturation=(high-low)/np.maximum(high,1)
  warmth=(values[:,:,0]-values[:,:,1])/np.maximum(high,1)
  weight=np.clip((.48-saturation)/.22,0,1)*np.clip((.24-warmth)/.10,0,1)*np.clip((high-40)/50,0,1)
  light=values.mean(axis=2)/225
  color=np.asarray(COLORS[player],np.float32)
  dyed=np.clip(light[:,:,None]*color,0,255)
  rgb[:]=np.clip(values*(1-weight[:,:,None])+dyed*weight[:,:,None],0,255).astype(np.uint8)
  del rgb
  return result
 def warm(self,skins):
  for theme in set(skins)-{'atari'}:
   for key in self.poses:self.source(theme,key)
 def frame(self,fighter,sprites,skin,scale=RENDER_SCALE):
  original,_,rect=sprites.frame(fighter)
  if skin=='atari':
   return pg.transform.scale(original,(original.get_width()*scale,original.get_height()*scale)),pg.Rect(rect.x*scale,rect.y*scale,rect.w*scale,rect.h*scale)
  item,face=sprites.record(fighter);key=(skin,item['image'],fighter.id,face,scale)
  meta=self.poses[item['image']];body=pg.Rect(meta['body_rect'])
  if face<0:body.x=original.get_width()-body.right
  if key not in self.frames:
   art=self.tint(self.source(skin,item['image']),fighter.id,skin)
   art=pg.transform.smoothscale(art,(body.w*scale,body.h*scale))
   if face<0:art=pg.transform.flip(art,True,False)
   self.frames[key]=art
   if len(self.frames)>160:self.frames.popitem(last=False)
  else:self.frames.move_to_end(key)
  art=self.frames[key]
  return art,art.get_rect(topleft=((rect.x+body.x)*scale,(rect.y+body.y)*scale))

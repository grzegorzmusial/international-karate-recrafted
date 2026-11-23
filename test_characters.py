"""Appearance choices and complete HD animation coverage, independent of combat."""
import os
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import json
import tempfile
from pathlib import Path
from collections import defaultdict
import unittest
import pygame as pg
from game import App,Sprites,Fighter,Arena,KEYS,FPS,ROOT,W,H
from characters import Characters,SKINS,RENDER_SCALE

class CharacterTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  pg.init();pg.display.set_mode((1280,720));cls.sprites=Sprites();cls.art=Characters(ROOT)
 @classmethod
 def tearDownClass(cls):pg.quit()
 def setUp(self):
  Path('work').mkdir(exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(dir='work');self.settings=Path(self.temp.name)/'settings.json';self.apps=[]
 def tearDown(self):
  for app in self.apps:app.pads.close()
  pg.mixer.stop();self.temp.cleanup()
 def app(self):
  app=App(windowed=True,settings_path=self.settings);self.apps.append(app);return app
 def pose(self,meta,face=1):
  move=meta['move'];f=Fighter(0,640,face,move='fall' if move.startswith('fall') else move,time=(meta['frame']+.001)/FPS,facing=face,reaction=move)
  if move in ('walk','backwalk','idle'):f.walktime=f.time
  return f
 def test_every_original_pose_has_hd_metadata(self):
  referenced={f['image'] for seq in self.sprites.data.values() for f in seq}
  self.assertEqual(referenced,set(self.art.poses));self.assertEqual(len(referenced),44)
 def test_complete_nonempty_transparent_art_for_every_theme_and_pose(self):
  for theme in ('original','ryu','ken'):
   for key,meta in self.art.poses.items():
    source=self.art.source(theme,key)
    self.assertGreater(source.get_width(),20);self.assertGreater(source.get_height(),20)
    self.assertGreater(pg.mask.from_surface(source).count(),300)
    for face in (-1,1):
     f=self.pose(meta,face);im,r=self.art.frame(f,self.sprites,theme)
     self.assertGreater(pg.mask.from_surface(im).count(),300)
     self.assertEqual(im.get_size(),(meta['body_rect'][2]*2,meta['body_rect'][3]*2))
 def test_appearance_does_not_change_native_combat_pixels_masks_or_state(self):
  for meta in self.art.poses.values():
   f=self.pose(meta);before,mask,rect=self.sprites.frame(f)
   pixels=pg.image.tobytes(before,'RGBA');count=mask.count();state=vars(f).copy()
   for theme in SKINS:self.art.frame(f,self.sprites,theme)
   after,new_mask,new_rect=self.sprites.frame(f)
   self.assertEqual(pixels,pg.image.tobytes(after,'RGBA'));self.assertEqual(count,new_mask.count());self.assertEqual(rect,new_rect);self.assertEqual(state,vars(f))
 def test_atari_option_keeps_the_exact_pixel_art(self):
  f=Fighter(0,640,1);source,_,rect=self.sprites.frame(f);im,r=self.art.frame(f,self.sprites,'atari')
  reduced=pg.transform.scale(im,source.get_size());self.assertEqual(pg.image.tobytes(source,'RGBA'),pg.image.tobytes(reduced,'RGBA'))
  self.assertEqual(r,pg.Rect(rect.x*2,rect.y*2,rect.w*2,rect.h*2))
 def test_keyboard_cycles_only_its_own_player(self):
  app=self.app()
  for i,(_,_,left,right,_) in enumerate(KEYS):
   app.skins=['original']*4;app.key(right);self.assertEqual(app.skins[i],'ryu');self.assertEqual(app.skins.count('original'),3)
   app.key(left);self.assertEqual(app.skins,['original']*4)
 def test_preset_toggles_original_and_ryu_ken(self):
  app=self.app();app.key(pg.K_F2);self.assertEqual(app.skins,['ryu','ken','ryu','ken'])
  app.key(pg.K_F2);self.assertEqual(app.skins,['original']*4)
 def test_appearance_selection_persists_after_reopening(self):
  app=self.app();app.choose_skin(0,1);app.choose_skin(1,2);app.choose_skin(3,-1)
  expected=app.skins.copy();self.assertEqual(self.app().skins,expected)
 def test_invalid_settings_fall_back_to_original(self):
  for saved in ['broken json',json.dumps({'skins':['unrecognized']*4}),json.dumps({'skins':['ryu']}),json.dumps([])]:
   self.settings.write_text(saved);self.assertEqual(self.app().skins,['original']*4)
 def test_mouse_selection_and_start_keep_chosen_characters(self):
  app=self.app();app.menu_click((800,329));self.assertEqual(app.skins[0],'ryu')
  app.menu_click((800,482));self.assertEqual(app.skins[3],'ryu')
  app.menu_click((640,613));self.assertEqual(app.state,'fight');self.assertEqual(app.skins,['ryu','original','original','ryu'])
 def test_fight_directions_do_not_change_character_choices(self):
  app=self.app();app.state='fight';before=app.skins.copy()
  for _,_,left,right,_ in KEYS:app.key(left);app.key(right)
  app.key(pg.K_F2);self.assertEqual(app.skins,before)
 def test_render_canvas_is_native_2560_by_1440(self):
  app=self.app();app.draw();self.assertEqual(app.render_canvas.get_size(),(W*2,H*2));self.assertEqual(RENDER_SCALE,2)
 def test_painting_cache_is_bounded(self):
  for player in range(4):
   for theme in ('original','ryu','ken'):
    for meta in self.art.poses.values():
     f=self.pose(meta);f.id=player;self.art.frame(f,self.sprites,theme)
  self.assertLessEqual(len(self.art.frames),160)
 def test_hd_image_is_continuous_at_landing_and_repeat_boundary(self):
  for theme in ('original','ryu','ken'):
   for horizontal in (-1,1):
    arena=Arena(self.sprites);f=arena.fighters[0];f.x=600;previous=None;landed=0
    for tick in range(110):
     arena.step(1/FPS,[(horizontal,-1,True),(0,0,False),(0,0,False),(0,0,False)])
     image,rect=self.art.frame(f,self.sprites,theme)
     if previous and f.time<previous[0]:
      self.assertEqual(rect,previous[1]);self.assertEqual(pg.image.tobytes(image,'RGBA'),previous[2]);landed+=1
     previous=(f.time,rect,pg.image.tobytes(image,'RGBA'))
    self.assertGreaterEqual(landed,2)

if __name__=='__main__':unittest.main(verbosity=2)

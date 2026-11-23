"""Regression checks for simultaneous four-player combat and endless sessions."""
import os
os.environ['SDL_VIDEODRIVER']='dummy';os.environ['SDL_AUDIODRIVER']='dummy'
import unittest
from collections import defaultdict
from game import *
IDLE=(0,0,False)
class FourPlayerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  pg.init();pg.display.set_mode((W,H));cls.sprites=Sprites()
 @classmethod
 def tearDownClass(cls):pg.quit()
 def setUp(self):self.a=Arena(self.sprites)
 def advance(self,n,commands=None):
  result=[]
  for _ in range(n):result+=self.a.step(1/FPS,commands or [IDLE]*4)
  return result
 def pair(self,aid=0,vid=1,distance=160):
  for i,f in enumerate(self.a.fighters):f.x=1050+i*25
  a=self.a.fighters[aid];v=self.a.fighters[vid];a.x=350;a.face=1;v.x=350+distance;v.face=-1
 def test_all_four_key_groups(self):
  for i,(up,down,left,right,fire) in enumerate(KEYS):
   keys=defaultdict(bool,{up:True,right:True,fire:True});cmd=inputs(keys)
   self.assertEqual(cmd[i],(1,-1,True));self.assertEqual(sum(c!=IDLE for c in cmd),1)
  self.assertEqual(inputs(defaultdict(bool,{pg.K_RCTRL:True}))[0],(0,0,True))
 def test_four_move_independently_together(self):
  before=[f.x for f in self.a.fighters];self.advance(15,[(1,0,False)]*4)
  self.assertTrue(all(f.x>x for f,x in zip(self.a.fighters,before)))
 def test_each_player_can_hit_each_other(self):
  for aid in range(4):
   for vid in range(4):
    if aid==vid:continue
    self.a=Arena(self.sprites);self.pair(aid,vid);cmd=[IDLE]*4;cmd[aid]=(0,1,False)
    self.assertIn((aid,vid),self.advance(40,cmd))
 def test_miss_out_of_range(self):
  self.pair(distance=480);self.assertEqual(self.advance(50,[(0,1,False),IDLE,IDLE,IDLE]),[])
 def test_cannot_hit_behind_with_front_sweep(self):
  self.pair(distance=-160);self.assertEqual(self.advance(50,[(0,1,False),IDLE,IDLE,IDLE]),[])
 def test_sweep_hits_both_stances(self):
  for face in (1,-1):
   self.a=Arena(self.sprites);self.pair();self.a.fighters[1].face=face
   self.assertIn((0,1),self.advance(40,[(0,1,False),IDLE,IDLE,IDLE]))
 def test_victim_falls_gets_up_and_stays_human(self):
  self.pair();self.advance(25,[(0,1,False),IDLE,IDLE,IDLE]);v=self.a.fighters[1]
  self.assertEqual(v.move,'fall');self.assertEqual(v.received,1)
  self.advance(200);self.assertEqual(v.move,'idle')
  before=v.x;self.advance(10,[IDLE,(1,0,False),IDLE,IDLE]);self.assertGreater(v.x,before)
 def test_two_separate_pairs_fight_simultaneously(self):
  for f,x,face in zip(self.a.fighters,(190,350,850,1010),(1,-1,1,-1)):f.x=x;f.face=face
  hits=self.advance(45,[(0,1,False),IDLE,(0,1,False),IDLE])
  self.assertIn((0,1),hits);self.assertIn((2,3),hits)
 def test_simultaneous_attacks_are_not_order_dependent(self):
  self.pair();hits=self.advance(45,[(0,1,False),(0,1,False),IDLE,IDLE])
  self.assertIn((0,1),hits);self.assertIn((1,0),hits)
 def test_roundhouse_preserves_facing(self):
  self.advance(100,[(-1,0,True),IDLE,IDLE,IDLE]);self.assertEqual(self.a.fighters[0].face,1)
 def test_back_lunge_can_turn_to_another_opponent(self):
  self.advance(100,[(-1,-1,False),IDLE,IDLE,IDLE]);self.assertEqual(self.a.fighters[0].face,-1)
 def test_held_flying_kick_always_lands(self):
  f=self.a.fighters[0];landings=0;previous_time=0;previous_bottom=FLOOR
  for _ in range(180):
   self.a.step(1/FPS,[(0,-1,True),IDLE,IDLE,IDLE])
   if f.time<previous_time:
    landings+=1;self.assertLessEqual(abs(previous_bottom-FLOOR),8)
   previous_time=f.time;_,_,r=self.sprites.frame(f);previous_bottom=r.bottom
  self.assertGreaterEqual(landings,4);self.assertGreater(f.x,170)
 def test_endless_scores_and_no_ai_or_bonus_states(self):
  self.a.fighters[0].score=99999;before=[f.x for f in self.a.fighters]
  self.advance(18000)
  self.assertEqual(self.a.fighters[0].score,99999);self.assertEqual([f.x for f in self.a.fighters],before)
  self.assertTrue(all(f.move=='idle' for f in self.a.fighters));self.assertGreater(self.a.elapsed,300)
 def test_every_native_animation_is_complete_rgba_without_background(self):
  for move,seq in self.sprites.data.items():
   self.assertTrue(seq)
   for item in seq:
    im=pg.image.load(str(ROOT/'assets/frames'/f"{item['image']}.png"))
    self.assertGreater(im.get_bounding_rect().width,0)
    self.assertLessEqual(im.get_height(),96)
    for x in range(im.get_width()):
     for y in range(im.get_height()):
      c=im.get_at((x,y))
      if c.a:self.assertIn(c[:3],[(213,210,213),(189,113,123),(0,4,0)])
 def test_fullscreen_is_default_pause_and_menu_do_not_change_scores(self):
  app=App();self.assertTrue(app.fullscreen);self.assertTrue(app.screen.get_flags()&pg.FULLSCREEN)
  app.reset();app.arena.fighters[0].score=1000;app.key(pg.K_p);self.assertTrue(app.paused)
  app.key(pg.K_ESCAPE);self.assertEqual(app.state,'menu');self.assertEqual(app.arena.fighters[0].score,1000)
 def colored_bounds(self,f):
  im,_,rect=self.sprites.frame(f)
  pts=[(x,y) for x in range(im.get_width()) for y in range(im.get_height()) if im.get_at((x,y)).a and im.get_at((x,y))[:3]!=(0,4,0)]
  xs,ys=zip(*pts)
  return pg.Rect(min(xs)+rect.x,min(ys)+rect.y,max(xs)-min(xs)+1,max(ys)-min(ys)+1)
 def test_fall_starts_upright_and_contains_all_collapse_phases(self):
  for reaction in ('fall','fall_low'):
   f=Fighter(1,600,-1,move='fall',facing=-1,reaction=reaction)
   states=[]
   for frame in (0,6,13,20,27):
    f.time=(frame+.001)/FPS;states.append(self.colored_bounds(f))
   self.assertGreater(states[0].height,150)
   self.assertLess(states[-1].height,70)
   self.assertGreater(states[-1].top,states[0].top+100)
   self.assertGreaterEqual(len({(r.width,r.height,r.top) for r in states}),4)
 def test_native_contact_to_floor_delay_is_preserved_frame_by_frame(self):
  for reaction in ('fall','fall_low'):
   seq=self.sprites.data[reaction];start=seq[0]['native_frame']
   self.assertEqual([item['native_frame'] for item in seq[:109]],list(range(start,start+109)))
   f=Fighter(1,600,-1,move='fall',facing=-1,reaction=reaction)
   first_prone=None
   for frame in range(40):
    f.time=(frame+.001)/FPS
    if self.colored_bounds(f).height<70:first_prone=frame;break
   self.assertEqual(first_prone,27)
 def test_recovery_has_intermediate_poses_before_standing(self):
  f=Fighter(1,600,-1,move='fall',facing=-1,reaction='fall_low')
  heights=[]
  for frame in (108,115,122,129,135):
   f.time=(frame+.001)/FPS;heights.append(self.colored_bounds(f).height)
  self.assertLess(heights[0],70);self.assertGreater(heights[-1],150)
  self.assertGreaterEqual(len(set(heights)),4)
 def test_low_and_high_attacks_select_their_reaction(self):
  for command,expected in [((0,1,False),'fall_low'),((1,0,True),'fall')]:
   self.a=Arena(self.sprites);self.pair()
   self.advance(40,[command,IDLE,IDLE,IDLE]);v=self.a.fighters[1]
   self.assertEqual(v.move,'fall');self.assertEqual(v.reaction,expected)
 def test_knockback_follows_impact_even_when_hit_from_behind(self):
  self.pair();self.a.fighters[1].face=1
  self.advance(40,[(0,1,False),IDLE,IDLE,IDLE]);v=self.a.fighters[1]
  self.assertEqual(v.facing,-1);self.assertEqual(v.face,1)
  v.time=27.001/FPS
  self.assertGreater(self.colored_bounds(v).centerx,v.x)
 def test_reaction_does_not_award_repeated_points_during_collapse(self):
  self.pair();hits=self.advance(145,[(0,1,False),IDLE,IDLE,IDLE])
  self.assertEqual(hits.count((0,1)),1);self.assertEqual(self.a.fighters[0].score,1)
 def test_every_player_walks_through_every_other_player_both_directions(self):
  for aid in range(4):
   for vid in range(4):
    if aid==vid:continue
    for direction in (-1,1):
     self.a=Arena(self.sprites)
     self.a.fighters[aid].x=600-direction*100;self.a.fighters[vid].x=600
     cmd=[IDLE]*4;cmd[aid]=(direction,0,False)
     self.advance(70,cmd)
     self.assertGreater((self.a.fighters[aid].x-600)*direction,100)
 def test_two_walking_players_swap_sides(self):
  self.a.fighters[0].x=400;self.a.fighters[1].x=700
  self.advance(70,[(1,0,False),(-1,0,False),IDLE,IDLE])
  self.assertGreater(self.a.fighters[0].x,self.a.fighters[1].x)
 def test_exactly_overlapping_players_all_keep_moving(self):
  for f in self.a.fighters:f.x=600
  self.advance(20,[(1,0,False)]*4)
  self.assertTrue(all(f.x>650 for f in self.a.fighters))
 def test_flip_body_is_complete_in_every_frame(self):
  for move in ('flip','backflip'):
   seq=self.sprites.data[move]
   for item in seq:
    im=pg.image.load(str(ROOT/'assets/frames'/f"{item['image']}.png"))
    count=sum(im.get_at((x,y)).a>0 and im.get_at((x,y))[:3]!=(0,4,0) for x in range(im.get_width()) for y in range(im.get_height()))
    self.assertGreaterEqual(count,500)
   self.assertEqual(seq[0]['image'],seq[-1]['image'])
 def test_native_flip_distance_is_preserved_in_both_facings(self):
  for face in (-1,1):
   for relative,expected in [(1,376),(-1,-376)]:
    self.a=Arena(self.sprites);f=self.a.fighters[0];f.x=600;f.face=face
    self.advance(10,[(relative*face,-1,True),IDLE,IDLE,IDLE]);self.advance(60)
    self.assertEqual(f.move,'idle');self.assertAlmostEqual(f.x,600+expected*face)
 def test_no_position_or_image_jump_when_landing(self):
  for face in (-1,1):
   for move,relative in [('flip',1),('backflip',-1)]:
    self.a=Arena(self.sprites);f=self.a.fighters[0];f.x=600;f.face=face
    commands=[(relative*face,-1,True),IDLE,IDLE,IDLE]
    previous=None;landed=False
    for frame in range(65):
     self.a.step(1/FPS,commands if frame<10 else [IDLE]*4);im,_,r=self.sprites.frame(f)
     visible=pg.Surface(im.get_size());visible.fill((43,57,71));visible.blit(im,(0,0));pixels=pg.image.tobytes(visible,'RGB')
     if previous and previous[0]==move and f.move=='idle':
      self.assertAlmostEqual(f.x,previous[1]);self.assertEqual(r,previous[2]);self.assertEqual(pixels,previous[3]);landed=True
     previous=(f.move,f.x,r,pixels)
    self.assertTrue(landed)
 def test_airborne_poses_remain_fully_visible_at_both_edges(self):
  for face in (-1,1):
   for start in (105,1175):
    for command in [(face,-1,True),(-face,-1,True),(0,-1,False),(0,-1,True)]:
     self.a=Arena(self.sprites);f=self.a.fighters[0];f.x=start;f.face=face
     for _ in range(65):
      self.a.step(1/FPS,[command,IDLE,IDLE,IDLE]);_,_,r=self.sprites.frame(f)
      self.assertGreaterEqual(r.left,8);self.assertLessEqual(r.right,W-8)
      self.assertGreaterEqual(r.top,112);self.assertLessEqual(r.bottom,672)
 def test_held_flips_repeat_without_disappearing(self):
  for horizontal in (-1,1):
   self.a=Arena(self.sprites);f=self.a.fighters[0];f.x=600
   previous=0;landings=0
   for _ in range(180):
    self.a.step(1/FPS,[(horizontal,-1,True),IDLE,IDLE,IDLE])
    if f.time<previous:landings+=1
    previous=f.time;im,mask,r=self.sprites.frame(f)
    self.assertGreater(mask.count(),1000);self.assertGreaterEqual(r.left,8);self.assertLessEqual(r.right,W-8)
   self.assertGreaterEqual(landings,4);self.assertEqual(f.face,1)
 def test_forward_then_backward_flip_has_no_accumulated_teleport(self):
  f=self.a.fighters[0];f.x=400
  self.advance(10,[(1,-1,True),IDLE,IDLE,IDLE]);self.advance(52)
  self.advance(10,[(-1,-1,True),IDLE,IDLE,IDLE]);self.advance(50)
  self.assertEqual(f.move,'idle');self.assertAlmostEqual(f.x,400)
 def test_pass_through_does_not_disable_attack_collisions(self):
  self.pair();hits=self.advance(40,[(0,1,False),(-1,0,False),IDLE,IDLE])
  self.assertIn((0,1),hits)
 def test_detached_airborne_shadow_is_visible_but_cannot_receive_a_hit(self):
  for move,frame in [('flip',21),('backflip',16),('jump',16),('jumpkick',16)]:
   for face in (-1,1):
    f=Fighter(0,600,face,move=move,time=(frame+.001)/FPS,facing=face)
    im,body,rect=self.sprites.frame(f)
    ground=pg.mask.Mask(im.get_size());box=pg.Rect(0,FLOOR-8-rect.y,im.get_width(),16).clip(im.get_rect())
    ground.draw(pg.mask.Mask(box.size,fill=True),box.topleft)
    self.assertIsNotNone(pg.mask.from_surface(im).overlap(ground,(0,0)))
    self.assertIsNone(body.overlap(ground,(0,0)))
 def test_sweep_under_airborne_opponent_does_not_hit_the_shadow(self):
  self.a.fighters[0].x=450;self.a.fighters[0].move='sweep';self.a.fighters[0].time=.28;self.a.fighters[0].facing=1
  v=self.a.fighters[1];v.x=600;v.face=-1;v.facing=-1;v.move='flip';v.time=21/FPS
  item=self.sprites.data['flip'][21];v.motion_origin=v.x-item['travel']*4*v.facing
  hits=self.a.step(1/FPS,[IDLE]*4)
  self.assertNotIn((0,1),hits);self.assertEqual(v.move,'flip')
 def test_both_backward_fire_attacks_leave_all_players_turned(self):
  for player in range(4):
   for face in (-1,1):
    for relative in (0,-1):
     self.a=Arena(self.sprites);f=self.a.fighters[player];f.face=face;f.x=600
     cmd=[IDLE]*4;cmd[player]=(relative*face,1,True)
     self.advance(100,cmd);self.assertEqual(f.face,-face);self.assertEqual(f.move,'idle')
     self.advance(100);self.assertEqual(f.face,-face)
 def test_held_backward_diagonal_does_not_start_a_front_kick_after_turn(self):
  f=self.a.fighters[0];f.face=1;f.x=600;started=[];previous='idle'
  for _ in range(150):
   self.a.step(1/FPS,[(-1,1,True),IDLE,IDLE,IDLE])
   if f.move!='idle' and previous=='idle':started.append(f.move)
   previous=f.move
  self.assertEqual(started,['backshin']);self.assertEqual(f.face,-1)
 def test_releasing_then_pressing_fire_down_can_turn_again(self):
  self.advance(100,[(0,1,True),IDLE,IDLE,IDLE]);self.assertEqual(self.a.fighters[0].face,-1)
  self.advance(2);self.advance(100,[(0,1,True),IDLE,IDLE,IDLE]);self.assertEqual(self.a.fighters[0].face,1)
 def test_controls_after_turn_use_the_new_facing(self):
  self.advance(100,[(0,1,True),IDLE,IDLE,IDLE]);f=self.a.fighters[0];self.advance(2)
  self.advance(1,[(-1,0,True),IDLE,IDLE,IDLE]);self.assertEqual(f.move,'high');self.assertEqual(f.facing,-1)
 def test_direction_changes_only_at_the_end_of_a_completed_turning_move(self):
  for command,name in [((0,1,True),'backcrouch'),((-1,1,True),'backshin')]:
   self.a=Arena(self.sprites);f=self.a.fighters[0]
   self.advance(1,[command,IDLE,IDLE,IDLE]);self.assertEqual(f.move,name);self.assertEqual(f.face,1);self.assertEqual(f.facing,1)
   self.advance(100,[command,IDLE,IDLE,IDLE]);self.assertEqual(f.face,-1)
 def test_held_fire_up_repeats_for_all_players_in_both_facings(self):
  for player in range(4):
   for face in (-1,1):
    self.a=Arena(self.sprites);f=self.a.fighters[player];f.x=640;f.face=face
    keys=defaultdict(bool,{KEYS[player][0]:True,KEYS[player][4]:True});commands=inputs(keys)
    starts=0;previous_time=-1
    for _ in range(170):
     self.a.step(1/FPS,commands)
     self.assertEqual(f.move,'jumpkick')
     if f.time<previous_time:starts+=1
     previous_time=f.time
    self.assertGreaterEqual(starts,4);self.assertEqual(f.face,face)
 def test_releasing_fire_up_finishes_current_jump_and_stops_repeating(self):
  self.advance(60,[(0,-1,True),IDLE,IDLE,IDLE]);f=self.a.fighters[0]
  self.assertEqual(f.move,'jumpkick');self.advance(90)
  self.assertEqual(f.move,'idle');x=f.x;self.advance(100)
  self.assertEqual(f.move,'idle');self.assertEqual(f.x,x)
 def test_repeated_flying_kicks_stay_visible_at_both_edges(self):
  for face,start in [(-1,105),(1,1175)]:
   self.a=Arena(self.sprites);f=self.a.fighters[0];f.face=face;f.x=start
   for _ in range(450):
    self.a.step(1/FPS,[(0,-1,True),IDLE,IDLE,IDLE]);_,mask,r=self.sprites.frame(f)
    self.assertGreater(mask.count(),1000);self.assertGreaterEqual(r.left,8);self.assertLessEqual(r.right,W-8)
 def test_each_repeated_flying_kick_can_score_again(self):
  self.pair(distance=130);f=self.a.fighters[0];v=self.a.fighters[1];hits=0
  # Place a recovered target in range before each cycle, without resetting the attacker's latch.
  for cycle in range(3):
   v.move='idle';v.invuln=0;v.x=f.x+130
   for _ in range(40):hits+=self.a.step(1/FPS,[(0,-1,True),IDLE,IDLE,IDLE]).count((0,1))
  self.assertEqual(hits,3)
 def test_repeated_diagonal_fire_for_all_players_and_both_facings(self):
  for player in range(4):
   for face in (-1,1):
    for relative,move in [(1,'flip'),(-1,'backflip')]:
     self.a=Arena(self.sprites);f=self.a.fighters[player];f.x=640;f.face=face
     up,down,left,right,fire=KEYS[player]
     keys=defaultdict(bool,{up:True,fire:True,(right if relative*face>0 else left):True})
     cmd=inputs(keys);last=0;loops=0
     for _ in range(210):
      self.a.step(1/FPS,cmd);self.assertEqual(f.move,move)
      if f.time<last:loops+=1
      last=f.time
     self.assertGreaterEqual(loops,4);self.assertEqual(f.face,face)
 def test_releasing_diagonal_finishes_current_flip_and_stops(self):
  for horizontal in (-1,1):
   self.a=Arena(self.sprites);f=self.a.fighters[0];f.x=640
   self.advance(70,[(horizontal,-1,True),IDLE,IDLE,IDLE]);self.advance(100)
   self.assertEqual(f.move,'idle');x=f.x;self.advance(100);self.assertEqual(f.x,x)
 def test_repeated_flip_landing_is_continuous_and_native_rhythm(self):
  for horizontal in (-1,1):
   self.a=Arena(self.sprites);f=self.a.fighters[0];f.x=600;previous=None;loop_frames=[]
   for frame in range(210):
    self.a.step(1/FPS,[(horizontal,-1,True),IDLE,IDLE,IDLE]);im,_,r=self.sprites.frame(f)
    surface=pg.Surface(im.get_size());surface.fill((43,57,71));surface.blit(im,(0,0));pixels=pg.image.tobytes(surface,'RGB')
    if previous and f.time<previous[0]:
     loop_frames.append(frame)
     self.assertAlmostEqual(f.x,previous[1]);self.assertEqual(r,previous[2]);self.assertEqual(pixels,previous[3])
    previous=(f.time,f.x,r,pixels)
   self.assertGreaterEqual(len(loop_frames),4)
   self.assertTrue(all(40<=b-a<=41 for a,b in zip(loop_frames,loop_frames[1:])))
if __name__=='__main__':unittest.main(verbosity=2)

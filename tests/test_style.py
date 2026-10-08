import unittest,sys
import importlib.util, pathlib
spec=importlib.util.spec_from_file_location('style_renderer',pathlib.Path(__file__).resolve().parents[1]/'scripts'/'render.py')
renderer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
prepare_content,timing_plan,build_card,LANG = renderer.prepare_content,renderer.timing_plan,renderer.build_card,renderer.LANG
class StyleTests(unittest.TestCase):
 def test_timer_after_question(self):
  p=timing_plan(2,2,3)
  self.assertAlmostEqual(p['timer_start'],2.3)
  self.assertAlmostEqual(p['reveal']-p['timer_start'],3)
  self.assertGreaterEqual(p['total'],12)
 def test_missing_explanation_fails(self):
  with self.assertRaises(ValueError): prepare_content({'id':'unreviewed','question':'test','options':['a']*4,'correct_index':0})
 def test_long_speech_not_cut(self):
  with self.assertRaises(ValueError): timing_plan(8,5,7)
 def test_topic_not_inferred(self):
  q=prepare_content({'id':'custom','question':'A rights question','options':['a','b','c','d'],'correct_index':0,'explanation':'One checked explanation.','source_url':'https://example.org'})
  self.assertEqual(q['topic'],'')
  self.assertNotIn('FREEDOM STRUGGLE',build_card(q))
 def test_countdown_and_reveal(self):
  q=prepare_content({'id':'q0075' if LANG=='en' else 'q0061','question':'x','options':['a']*4,'correct_index':0})
  for n in (3,2,1):self.assertIn(f'class="number">{n}',build_card(q,'countdown',n))
  self.assertIn('option correct',build_card(q,'reveal'))
  self.assertIn(q['explanation'],build_card(q,'explain'))
if __name__=='__main__': unittest.main()

class ProductionStudioTests(unittest.TestCase):
 def test_production_uses_approved_studio(self):
  q=prepare_content({'id':'q0075' if LANG=='en' else 'q0062','question':'x','options':['a']*4,'correct_index':0})
  p=timing_plan(2,2,3)
  self.assertIn('studio-glow',renderer.studio_html(q,1,p))
  self.assertIn('FOLLOW FOR THE TRAP' if LANG=='en' else 'रोज़ एक सवाल',renderer.studio_html(q,p['why_start']+.1,p))
 def test_buffer_coverage(self):
  for id in (['q0075','q0077'] if LANG=='en' else ['q0062','q0063']):
   self.assertTrue(prepare_content({'id':id,'question':'x','options':['a']*4,'correct_index':0})['source_url'].startswith('https://'))

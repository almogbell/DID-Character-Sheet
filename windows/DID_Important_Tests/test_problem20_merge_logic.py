from __future__ import annotations
import unittest
from copy import deepcopy
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mobile_sync_merge import merge_characters

class ThreeWayMergeTests(unittest.TestCase):
    def setUp(self):
        self.base={
            'id':'hero', 'name':'Aurora',
            'HP':{'current_HP':8,'max_HP':12},
            'Adversity':{'current_AT':2,'max_AT':5},
            'inventory':{'list_of_items':[{'id':'potion','name':'Potion','quantity':1,'description':'Heal'}]},
            'notes':{'list_of_notes':[{'id':'one','title':'Quest','text':'original'}]},
            'progression':{'level':1,'current_IP':6},
        }
    def merge(self,pc=None,phone=None,choice=None):
        return merge_characters(self.base,pc or deepcopy(self.base),phone or deepcopy(self.base),hp_at_choice=choice)
    def test_independent_new_items_auto_merge(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['inventory']['list_of_items'].append({'id':'pc','name':'Rope','quantity':1})
        h['inventory']['list_of_items'].append({'id':'ph','name':'Sword','quantity':1})
        r=self.merge(p,h);self.assertEqual({x['id'] for x in r.merged['inventory']['list_of_items']},{'pc','ph','potion'})
    def test_notes_in_different_ids_merged(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['notes']['list_of_notes'][0]['text']='PC note'
        h['notes']['list_of_notes'].append({'id':'two','title':'Loot','text':'Phone note'})
        r=self.merge(p,h).merged;self.assertEqual(r['notes']['list_of_notes'][0]['text'],'PC note');self.assertEqual(len(r['notes']['list_of_notes']),2)
    def test_both_edit_same_note_keeps_two(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['notes']['list_of_notes'][0]['text']='PC'
        h['notes']['list_of_notes'][0]['text']='Phone'
        r=self.merge(p,h).merged['notes']['list_of_notes']
        self.assertEqual(len(r),2);self.assertEqual({x['text'] for x in r},{'PC','Phone'})
        self.assertNotEqual(r[0]['id'],r[1]['id'])
    def test_additive_quantity_no_duplicate(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['inventory']['list_of_items'][0]['quantity']=3
        h['inventory']['list_of_items'][0]['quantity']=2
        r=self.merge(p,h).merged['inventory']['list_of_items']
        self.assertEqual(len(r),1);self.assertEqual(r[0]['quantity'],4)
    def test_both_increment_same_item_counts_both_increments(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['inventory']['list_of_items'][0]['quantity']=2
        h['inventory']['list_of_items'][0]['quantity']=2
        result=self.merge(p,h).merged['inventory']['list_of_items']
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['quantity'],3)
    def test_independent_fields_of_same_item(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['inventory']['list_of_items'][0]['description']='New PC'
        h['inventory']['list_of_items'][0]['quantity']=4
        r=self.merge(p,h).merged['inventory']['list_of_items']
        self.assertEqual(len(r),1);self.assertEqual(r[0]['quantity'],4);self.assertEqual(r[0]['description'],'New PC')
    def test_same_item_text_conflict_keeps_two(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['inventory']['list_of_items'][0]['description']='PC'
        h['inventory']['list_of_items'][0]['description']='Phone'
        r=self.merge(p,h).merged['inventory']['list_of_items']
        self.assertEqual(len(r),2)
        self.assertEqual({x['description'] for x in r},{'PC','Phone'})
    def test_remove_and_edit_preserves_edit(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['notes']['list_of_notes']=[]
        h['notes']['list_of_notes'][0]['text']='Changed'
        r=self.merge(p,h).merged['notes']['list_of_notes']
        self.assertEqual(len(r),1);self.assertEqual(r[0]['text'],'Changed')
    def test_mutual_delete(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['notes']['list_of_notes']=[];h['notes']['list_of_notes']=[]
        self.assertEqual(self.merge(p,h).merged['notes']['list_of_notes'],[])
    def test_hp_conflict_only_requires_choice(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['HP']['current_HP']=7;h['HP']['current_HP']=6
        h['inventory']['list_of_items'].append({'id':'sword','name':'Sword','quantity':1})
        self.assertEqual(self.merge(p,h).conflicting_resources,('HP',))
        for choice,expected in [('pc',7),('phone',6)]:
            r=self.merge(p,h,choice=choice).merged
            self.assertEqual(r['HP']['current_HP'],expected)
            self.assertEqual(len(r['inventory']['list_of_items']),2)
    def test_at_conflict_only_requires_choice(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['Adversity']['current_AT']=3;h['Adversity']['current_AT']=4
        self.assertEqual(self.merge(p,h).conflicting_resources,('AT',))
    def test_only_phone_hp_changes_no_prompt(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        h['HP']['current_HP']=3
        self.assertEqual(self.merge(p,h).merged['HP']['current_HP'],3)
    def test_only_pc_hp_changes_no_prompt(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['HP']['current_HP']=9
        self.assertEqual(self.merge(p,h).merged['HP']['current_HP'],9)
    def test_same_changes_no_prompt(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['HP']['current_HP']=5;h['HP']['current_HP']=5
        self.assertEqual(self.merge(p,h).merged['HP']['current_HP'],5)
    def test_wrong_character_id_rejected(self):
        h=deepcopy(self.base);h['id']='other'
        with self.assertRaises(ValueError): self.merge(phone=h)
    def test_invalid_resolution_rejected(self):
        with self.assertRaises(ValueError): self.merge(choice='overwrite')
    def test_merge_is_repeatable(self):
        p=deepcopy(self.base);h=deepcopy(self.base)
        p['notes']['list_of_notes'][0]['text']='PC';h['notes']['list_of_notes'][0]['text']='Phone'
        self.assertEqual(self.merge(p,h).merged,self.merge(p,h).merged)

if __name__=='__main__':unittest.main()

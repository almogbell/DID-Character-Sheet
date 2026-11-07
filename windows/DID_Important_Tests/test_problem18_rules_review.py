import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from campaign_rules_review import inspect_character, apply_minimums

class FakeHP:
    def __init__(self, hearts): self.max_hearts = hearts; self.recalc = 0
    def recalculate(self): self.recalc += 1

class Character:
    def __init__(self, level=1, total=6, hearts=2, at=4):
        self.progression = NS(level=level, current_IP=total, used_IP=total)
        self.HP = FakeHP(hearts)
        self.adversity = NS(max_AT=at)
        self.free_heightened_ability_slots=2
    def set_level(self, level):
        self.progression.current_IP += (level-self.progression.level)*2
        self.progression.level = level

class ReviewTests(unittest.TestCase):
    def rules(self, **kw):
        return NS(level=kw.get('level',1), extra_ip=kw.get('extra_ip',0),
                  starting_hearts=kw.get('starting_hearts',None),starting_at=kw.get('starting_at',None),
                  free_heightened_ability_slots=kw.get('free_heightened_ability_slots',2))

    def test_one_new_ip_is_6_to_7(self):
        c=Character()
        r=inspect_character(c,self.rules(extra_ip=1))
        self.assertEqual([x.label for x in r.shortfalls],['total_ip'])
        self.assertEqual(apply_minimums(c,r),('total_ip',))
        self.assertEqual((c.progression.used_IP,c.progression.current_IP),(6,7))
        self.assertEqual(apply_minimums(c,r),())

    def test_no_downward_adjustments(self):
        c=Character(level=4,total=15,hearts=5,at=7)
        r=inspect_character(c,self.rules(level=2,extra_ip=1, starting_hearts=2,starting_at=4))
        self.assertFalse(r.can_auto_adjust)
        self.assertEqual(apply_minimums(c,r),())
        self.assertEqual((c.progression.level,c.progression.current_IP,c.HP.max_hearts,c.adversity.max_AT),(4,15,5,7))

    def test_level_increase_does_not_double_grant_ip(self):
        c=Character(level=1,total=6)
        r=inspect_character(c,self.rules(level=3,extra_ip=1))
        self.assertEqual(apply_minimums(c,r),('level','total_ip'))
        self.assertEqual(c.progression.current_IP,11)
        self.assertEqual(apply_minimums(c,r),())

    def test_hearts_and_at_increase_only(self):
        c=Character(hearts=2,at=3)
        r=inspect_character(c,self.rules(starting_hearts=3,starting_at=5))
        self.assertEqual(set(apply_minimums(c,r)),{'max_hearts','max_at'})
        self.assertEqual(c.HP.max_hearts,3)
        self.assertEqual(c.HP.recalc,1)
        self.assertEqual(c.adversity.max_AT,5)

    def test_restricted_choices_not_silently_fixed(self):
        c=Character()
        r=inspect_character(c,self.rules(),('Improvement list does not match the campaign rules.',))
        self.assertFalse(r.can_auto_adjust)
        self.assertIn('Improvement list',r.manual_issues[0])

    def test_nonmatching_free_heightened_requires_manual(self):
        c=Character()
        r=inspect_character(c,self.rules(free_heightened_ability_slots=3))
        self.assertFalse(r.can_auto_adjust)
        self.assertIn('choose manually',r.manual_issues[0])

if __name__=='__main__':unittest.main()

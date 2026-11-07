from backend_2_1 import Character, StatSystem, ImprovementSystem, STAT_NAMES

def character(free=0, ip=30):
    c = Character(id='test')
    c.free_heightened_ability_slots = free
    c.progression.current_IP = ip
    c.validate()
    return c

def buy(c, name):
    return ImprovementSystem.add_from_catalog(c, 'heightened_ability', {'stat_name': name})

a,b = STAT_NAMES[:2]
c = character()
for tier in range(1,5):
    assert buy(c,a)
    assert c.progression.used_IP == tier*(tier+1)//2
    assert c.improvements.list_of_taken_improvements[-1].cost == tier
assert buy(c,b) and c.progression.used_IP == 11
assert not ImprovementSystem.remove_improvement(c,c.improvements.list_of_taken_improvements[0].id)
assert ImprovementSystem.remove_improvement(c,c.improvements.list_of_taken_improvements[3].id)
assert c.progression.used_IP == 7
c.validate(); assert c.progression.used_IP == 7
c = character(ip=2)
assert buy(c,a)
assert not buy(c,a)
assert c.stats.get_stat(a).bonus == 1 and c.progression.used_IP == 1
c = character(free=2)
assert StatSystem.add_free_heightened_ability(c,a)
assert c.progression.used_IP == 0
assert StatSystem.add_free_heightened_ability(c,a)
assert c.progression.used_IP == 1
assert c.free_heightened_ability_stats == [a,a]
assert c.stats.get_stat(a).bonus == 2
assert not StatSystem.add_free_heightened_ability(c,b)
assert buy(c,a)
assert c.progression.used_IP == 4
assert not StatSystem.remove_free_heightened_ability(c,a)
assert not StatSystem.set_free_heightened_stats(c,[b])
assert ImprovementSystem.remove_improvement(c,c.improvements.get_by_catalog_id("heightened_ability")[-1].id)
assert c.progression.used_IP == 1
assert StatSystem.remove_free_heightened_ability(c,a)
assert c.progression.used_IP == 0
c = character(free=2,ip=1)
assert StatSystem.add_free_heightened_ability(c,a)
assert StatSystem.add_free_heightened_ability(c,a)
assert c.progression.used_IP == 1
assert not StatSystem.add_free_heightened_ability(c,b)
assert not ImprovementSystem.add_from_catalog(c,'heightened_ability',{'stat_name':'Missing'})
print('Heightened Ability cost, affordability, duplicate free choice, mixed purchase, refund and revalidation checks passed.')

c = character(free=2)
assert StatSystem.add_free_heightened_ability(c,a)
assert StatSystem.add_free_heightened_ability(c,b)
assert not StatSystem.add_free_heightened_ability(c,STAT_NAMES[2])
assert len(c.free_heightened_ability_stats) == 2
c.free_heightened_ability_stats = [a,a,b,a]
c.validate()
assert c.free_heightened_ability_stats == [a,a]
assert c.stats.get_stat(a).bonus == 3
assert c.stats.get_stat(b).bonus == 1
assert c.progression.used_IP == 5
assert len(c.improvements.get_by_catalog_id('heightened_ability')) == 2
c.validate()
assert len(c.improvements.get_by_catalog_id('heightened_ability')) == 2
print('Free limit and legacy paid-bonus migration checks passed.')

c = character(free=2, ip=3)
assert buy(c,a)
assert not StatSystem.add_free_heightened_ability(c,a)
assert not StatSystem.set_free_heightened_stats(c,[a])
assert c.progression.used_IP == 1
assert c.stats.get_stat(a).bonus == 1
assert StatSystem.add_free_heightened_ability(c,b)
assert c.progression.used_IP == 1
print('Free reassignment cannot reprice paid purchases: passed.')

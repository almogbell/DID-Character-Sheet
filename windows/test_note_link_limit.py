"""Run from this folder or pass the app folder as the first argument."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as N
path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
source=ast.parse((path/'notes_ui.py').read_text(encoding='utf-8'))
f=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='can_link_note')
ns={};exec(compile(ast.Module(body=[f],type_ignores=[]),'<limit>','exec'),ns)
can=ns['can_link_note']
def note(i,target='',title='Player'):return N(id=str(i),title=title,linked_improvement_id=target)
for catalog in ['ordinary','spellcasting','magic_novice','mighty','sneak_attack','animal_buddy']:
 c=N(notes=N(list_of_notes=[]),improvements=N(list_of_taken_improvements=[N(id='imp',catalog_id=catalog)]))
 limit=3 if catalog=='ordinary' else 2
 for count in range(5):
  c.notes.list_of_notes=[note(i,'imp') for i in range(count)]
  assert can(c,note('new'),'imp')==(count<limit),(catalog,count)
  assert can(c,note('new'),'')
  if count:assert can(c,c.notes.list_of_notes[0],'imp')
 if catalog!='ordinary':
  title={'spellcasting':'Spellcasting Verbs','magic_novice':'Spellcasting Verbs','mighty':'Mighty','sneak_attack':'Sneak Attack','animal_buddy':'Animal Buddy'}[catalog]
  c.notes.list_of_notes=[note('sys','imp',title),note(1,'imp')]
  assert can(c,note('new'),'imp')
  c.notes.list_of_notes.append(note(2,'imp'))
  assert not can(c,note('new'),'imp')
for count in range(5):
 c.notes.list_of_notes=[note(i,'item:abc') for i in range(count)]
 assert can(c,note('new'),'item:abc')==(count<3)
print('PASS: limits for all five system improvements, ordinary improvements, items, unlinking, and existing links')

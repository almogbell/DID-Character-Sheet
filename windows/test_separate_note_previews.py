"""Run beside the patched frontend, or pass your app folder as argument."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS
path = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
source = ast.parse((path/'frontend_2_8.py').read_text(encoding='utf-8'))
method = next(n for n in ast.walk(source) if isinstance(n, ast.FunctionDef) and n.name=='open_linked_improvement_notes')
class Dialog:
    def __init__(self,title,body,**kw): self.title,self.body,self.color=title,body,kw['color_key']
    def close(self): pass
    def show(self): pass
    def raise_(self): pass
ns={'FantasyTemporaryNoteDialog':Dialog}
exec(compile(ast.Module(body=[method],type_ignores=[]),'<preview>','exec'),ns)
def note(id,title,text,color): return NS(id=id,title=title,text=text,color=color,linked_improvement_id='imp')
notes=[note('sys','Spellcasting Verbs','<b>Agility</b>','blue'),note('a','Magic','PLAYER A','purple'),note('b','Other','PLAYER B','#123456'),note('c','Fourth','FOURTH','red')]
chosen=[]
app=NS(character=NS(notes=NS(list_of_notes=notes)),position_improvement_note_popup=lambda *a:None,choose_linked_improvement_note=lambda items,anchor: chosen.extend(items),open_animal_buddy_note_popup=lambda *a:chosen.append('buddy'))
run=ns['open_linked_improvement_notes']
for n in notes:
    run(app,'imp',note_id=n.id)
    d=app._improvement_note_preview
    assert (d.title,d.body,d.color)==(n.title,n.text,n.color)
run(app,'imp')
assert chosen==notes
before=app._improvement_note_preview
run(app,'imp',note_id='missing')
assert app._improvement_note_preview is before
notes.append(note('buddy','Animal Buddy','buddy','green'))
run(app,'imp',note_id='buddy')
assert chosen[-1]=='buddy'
print('PASS: separate content, per-note colors, four-note selection, stale ID, buddy routing')

rich = note("rich", "Formatted", "<!--DID_RICH_NOTE--><b>Bold</b> <i>Italic</i> <u>Underline</u>", "purple")
notes.append(rich)
run(app, "imp", note_id="rich")
assert app._improvement_note_preview.body == rich.text
assert app._improvement_note_preview.color == "purple"
print("PASS: formatted player preview preserves emphasis and color")

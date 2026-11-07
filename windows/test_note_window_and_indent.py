"""Run: python test_note_window_and_indent.py APP_FOLDER"""
import os, sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
if len(sys.argv)>1:sys.path.insert(0,str(Path(sys.argv[1]).resolve()))
from types import SimpleNamespace as NS
from PySide6.QtWidgets import QApplication,QWidget,QPushButton,QLabel
from PySide6.QtCore import QObject,QEvent
from backend_2_1 import CharacterNote
from notes_ui import NoteCard,format_system_note_html
import frontend_2_8 as f
app=QApplication.instance() or QApplication([])
class Watch(QObject):
 def __init__(self):super().__init__();self.stray=[]
 def eventFilter(self,obj,event):
  if event.type()==QEvent.Type.Show and isinstance(obj,QPushButton) and obj.isWindow():self.stray.append(obj.text())
  return False
watch=Watch();app.installEventFilter(watch)
parent=QWidget();parent.show()
for i in range(5):
 card=NoteCard(CharacterNote(id=str(i),title='Player'),lambda:None,lambda *_:None,parent)
 card.show();app.processEvents()
 assert not card.link_btn.isWindow()
 card.close()
assert not watch.stray,watch.stray
f.QWebEngineView=None
f.MainWindow.check_for_recovery_on_startup=lambda self:None
window=f.MainWindow()
imp=NS(catalog_id='spellcasting',empowerments=[],id='spell')
window.open_improvement_note_preview(imp)
body=next(label.text() for label in window._improvement_note_preview.findChildren(QLabel) if '<p style=' in label.text())
assert body==format_system_note_html(window.spellcasting_note_html(imp))
window.close_improvement_note_preview()
note=CharacterNote(id='m',title='Mighty',text='<b>Benefits</b>\n• <b>Power:</b> Long explanation\nordinary line',linked_improvement_id='imp')
window.character.notes.list_of_notes.append(note)
window.open_linked_improvement_notes('imp',note_id='m')
body=next(label.text() for label in window._improvement_note_preview.findChildren(QLabel) if '<p style=' in label.text())
assert body==format_system_note_html(note.text)
assert 'text-indent:-15px' in body
window.close_improvement_note_preview();window.unsaved_changes=False;window.close();parent.close()
print('PASS: five new notes without stray top-level buttons; built-in and linked system previews use the Notes formatter')

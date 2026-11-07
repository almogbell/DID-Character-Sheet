"""Run: python test_ui_feedback.py APP_FOLDER (requires PySide6)."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from pathlib import Path
if len(sys.argv)>1:
    sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
import base64
import time
import unittest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QTimer, Qt, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QImage, QColor, QTextCursor, QFont
from PySide6.QtTest import QTest
from ui_feedback import run_loading_task, BusyNotice, LoadingRing, cached_portrait
from backend_2_1 import CharacterNote
from notes_ui import NoteCard
import ui_theme
APP = QApplication.instance() or QApplication([])

class FeedbackTests(unittest.TestCase):
    def test_slow_task_keeps_ui_ticking_and_shows_ring(self):
        owner=QWidget();owner.show()
        samples=[]
        timer=QTimer();timer.setInterval(30)
        timer.timeout.connect(lambda: samples.append([(w.isVisible(),w.findChild(LoadingRing).angle) for w in APP.topLevelWidgets() if isinstance(w,BusyNotice)]))
        timer.start()
        result=run_loading_task(owner,'Loading test…',lambda:(time.sleep(.42),42)[1])
        timer.stop()
        self.assertEqual(result,42)
        self.assertGreater(len(samples),5)
        angles=[angle for sample in samples for visible,angle in sample if visible]
        self.assertGreater(len(set(angles)),1)
        self.assertTrue(owner.isEnabled())
        self.assertFalse(any(w.isVisible() for w in APP.topLevelWidgets() if isinstance(w,BusyNotice)))
        owner.close()

    def test_fast_task_and_exception_cleanup(self):
        owner=QWidget();owner.show()
        self.assertEqual(run_loading_task(owner,'Quick',lambda:7),7)
        def fail():raise ValueError('sample failure')
        with self.assertRaisesRegex(ValueError,'sample failure'):
            run_loading_task(owner,'Error',fail)
        self.assertTrue(owner.isEnabled())
        owner.close()

    def test_cache_hit_preserves_pixels(self):
        img=QImage(20,20,QImage.Format.Format_ARGB32);img.fill(QColor('white'))
        img.setPixelColor(0,0,QColor(0,0,0,0))
        data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly);img.save(buffer,'PNG')
        uri='data:image/png;base64,'+base64.b64encode(bytes(data)).decode()
        a=cached_portrait(uri,20,20);b=cached_portrait(uri,20,20)
        self.assertEqual(a.cacheKey(),b.cacheKey())
        self.assertEqual(a.toImage().pixelColor(0,0).alpha(),0)
        self.assertEqual(a.toImage().pixelColor(10,10),QColor('white'))
        self.assertEqual(cached_portrait(uri,40,30).size().width(),40)

    def test_rich_note_shortcuts_save_and_reopen(self):
        note=CharacterNote(id='format',title='Player',text='Hello world')
        card=NoteCard(note,lambda:None,lambda *_:None);card.show();APP.processEvents()
        editor=card.text_edit;editor.setFocus();editor.selectAll();APP.processEvents()
        for key in (Qt.Key.Key_B,Qt.Key.Key_I,Qt.Key.Key_U):
            QTest.keyClick(editor,key,Qt.KeyboardModifier.ControlModifier)
        self.assertIn('<b>',note.text);self.assertIn('<i>',note.text);self.assertIn('<u>',note.text)
        self.assertFalse(hasattr(card,'format_bar'))
        second=NoteCard(note,lambda:None,lambda *_:None)
        cursor=second.text_edit.textCursor();cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
        fmt=cursor.charFormat()
        self.assertTrue(fmt.fontItalic());self.assertTrue(fmt.fontUnderline())
        self.assertGreaterEqual(fmt.fontWeight(),QFont.Weight.Bold)
        self.assertEqual(second.text_edit.toPlainText(),'Hello world')
        card.close();second.close()

    def test_ring_renders_in_both_themes(self):
        for theme in ('light','dark'):
            ui_theme.set_runtime_theme(theme)
            ring=LoadingRing();ring.show();APP.processEvents()
            self.assertFalse(ring.grab().isNull());ring.close()
        ui_theme.set_runtime_theme('light')

if __name__=='__main__':
    unittest.main(argv=[sys.argv[0]],verbosity=2)

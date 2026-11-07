"""Update only obsolete exact-layout assertions in 1.0.14 UI regression tests.

No tests are removed or skipped; assertions verify the new toolbar geometry.
Existing unknown test changes are left untouched.
"""
from pathlib import Path
from datetime import datetime
import shutil
import sys

ROOT=Path(__file__).resolve().parent
REPLACEMENTS={
 'test_1_0_14_campaign_reveals.py': [
  ("self.assertIn('tabs_host.setFixedWidth(280)', ui)",
   "self.assertIn('toolbar.insertWidget(0, tabs_host)', ui)"),
  ("self.assertIn('root.addWidget(tabs_host, 0, Qt.AlignmentFlag.AlignLeft)', ui)",
   "self.assertIn('root.addWidget(self._campaign_actions_host, 0, Qt.AlignmentFlag.AlignRight)', ui)"),
 ],
 'test_1_0_14_ui_followup.py': [
  ("self.assertIn('button.fontMetrics().horizontalAdvance(button.text()) + 42',s)",
   "self.assertIn('button.fontMetrics().horizontalAdvance(button.text()) + 30',s)"),
 ],
 'test_1_0_14_player_polish_7.py': [
  ('''        self.assertIn('button.setFixedSize(182, 40)', SRC)
        self.assertIn('for button in (help_button, refresh):', SRC)
        self.assertIn('self.refresh_btn.setText("Loading…")\\n        self.refresh_btn.setFixedSize(182, 40)', SRC)
        self.assertIn('self.refresh_btn.setText("Refresh")\\n        self.refresh_btn.setFixedSize(182, 40)', SRC)''',
   '''        self.assertIn('button.setFixedSize(help_width, 38)', SRC)
        self.assertIn('self._resize_campaign_tabs()', SRC)
        self.assertIn('toolbar.insertWidget(0, tabs_host)', SRC)
        self.assertNotIn('self.refresh_btn.setFixedSize(182, 40)', SRC)'''),
 ],
}

def main():
    count=0
    for filename, pairs in REPLACEMENTS.items():
        p=ROOT/'DID_Important_Tests'/filename
        if not p.is_file(): continue
        text=p.read_text(encoding='utf8')
        changed=text
        for old,new in pairs:
            if old in changed:
                changed=changed.replace(old,new)
        if changed!=text:
            backup=p.with_name(p.name+'.before_toolbar_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.bak')
            shutil.copy2(p,backup)
            p.write_text(changed,encoding='utf8')
            count+=1
            print('Updated obsolete layout assertion:',filename,'backup:',backup.name)
    print(f'Updated {count} test file(s); all other tests unchanged.')
    return 0
if __name__=='__main__':sys.exit(main())

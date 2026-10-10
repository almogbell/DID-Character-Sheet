from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


REPLACEMENTS = (
    (
        '        self.resize(980, 760)\n        self.setMinimumSize(860, 660)\n',
        '        self.resize(980, 660)\n        self.setMinimumSize(860, 610)\n',
        'window size',
    ),
    (
        '        root.setContentsMargins(24, 20, 24, 18)\n        root.setSpacing(10)\n',
        '        root.setContentsMargins(24, 18, 24, 16)\n        root.setSpacing(9)\n',
        'root spacing',
    ),
    (
        '        self.campaign_pages = QStackedWidget()\n        root.addWidget(self.campaign_pages, 1)\n',
        '        self.campaign_pages = QStackedWidget()\n        self.campaign_pages.setFixedHeight(390)\n        root.addWidget(self.campaign_pages)\n',
        'campaign page height',
    ),
    (
        '        page1.setContentsMargins(22, 18, 22, 8)\n        page1.setSpacing(11)\n',
        '        page1.setContentsMargins(22, 12, 22, 6)\n        page1.setSpacing(9)\n',
        'campaign page spacing',
    ),
    (
        '        page1.addLayout(manage_row)\n        page1.addStretch()\n',
        '        page1.addLayout(manage_row)\n        page1.addSpacing(4)\n',
        'campaign page stretch',
    ),
    (
        '        page2.setContentsMargins(22, 18, 22, 8)\n        page2.setSpacing(11)\n',
        '        page2.setContentsMargins(22, 12, 22, 6)\n        page2.setSpacing(9)\n',
        'character page spacing',
    ),
    (
        '        page2.addWidget(self.privacy_pane)\n        page2.addStretch()\n',
        '        page2.addWidget(self.privacy_pane)\n        page2.addSpacing(4)\n',
        'character page stretch',
    ),
    (
        '        page3.setContentsMargins(22, 18, 22, 8)\n        page3.setSpacing(11)\n',
        '        page3.setContentsMargins(22, 12, 22, 6)\n        page3.setSpacing(9)\n',
        'rules page spacing',
    ),
    (
        '        self.rules_view.setMinimumHeight(330)\n        page3.addWidget(self.rules_view, 1)\n',
        '        self.rules_view.setMinimumHeight(265)\n        self.rules_view.setMaximumHeight(285)\n        page3.addWidget(self.rules_view)\n',
        'rules view height',
    ),
)


def find_project_root():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    for candidate in list(candidates):
        candidates.extend(candidate.parents[:4])

    seen = set()
    for root in candidates:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if (
            (root / 'frontend_2_8.py').is_file()
            and (root / 'campaign_ui.py').is_file()
            and (root / 'campaign_privacy.py').is_file()
            and (root / 'campaign_session.py').is_file()
        ):
            return root

    raise FileNotFoundError(
        'Could not find the Phase 6 DID project. Put this script in the phase6 '
        'folder inside your current code folder and run it there.'
    )


def main():
    root = find_project_root()
    path = root / 'campaign_ui.py'
    original = path.read_text(encoding='utf-8')
    text = original

    required = (
        'self.campaign_pages = QStackedWidget()',
        'Step {index + 1} of 3',
        'Open DM Dashboard',
        'Create New Character',
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(
            'Campaign v6 is not installed yet. Missing: ' + ', '.join(missing)
        )

    changed = []
    for old, new, label in REPLACEMENTS:
        if new in text:
            continue
        if old not in text:
            raise RuntimeError(
                f'Could not safely refine {label}; expected Campaign v6 block was not found.'
            )
        text = text.replace(old, new, 1)
        changed.append(label)

    if text != original:
        backup = path.with_name(path.name + '.before_campaign_v7_proportions')
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f'Backup: {backup.name}')
        path.write_text(text, encoding='utf-8')

    py_compile.compile(str(path), doraise=True)

    if changed:
        print('Campaign proportions: PASS')
        for label in changed:
            print(f'  - {label}')
    else:
        print('Campaign proportions: already installed')
    print('Compile: PASS')
    print('Restart frontend_2_8.py and reopen Campaign.')


if __name__ == '__main__':
    main()

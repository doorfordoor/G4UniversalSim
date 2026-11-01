"""Prepare a passive native QA host; do not launch or automate any UI."""
from pathlib import Path
base=Path(__file__).resolve().parent
source=(base/'host.py').read_text(encoding='utf-8')
source=source.replace('import argparse, dataclasses, hashlib, json, os, sys, time',
    'import argparse, dataclasses, hashlib, json, os, sys, time, subprocess')
source=source.replace('from PySide6.QtCore import QSettings, QTimer, QCoreApplication, QEvent',
    'from PySide6.QtCore import QSettings, QTimer, QCoreApplication, QEvent, QPoint, QRect')
source=source.replace('from PySide6.QtWidgets import QApplication, QDialog',
    'from PySide6.QtWidgets import QApplication, QDialog, QScrollArea')
source=source.replace("'fixture': 'Production MainWindow, isolated settings/history/recovery/runs; no input automation in host'",
    "'fixture': 'Production MainWindow, isolated settings/history/recovery/runs; passive observation only',\n"
    "    'head': subprocess.check_output(['git','-c','core.longpaths=true','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),\n"
    "    'python': sys.executable, 'host_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),\n"
    "    'pyvista': {'version': __import__('pyvista').__version__, 'file': __import__('pyvista').__file__}")
source=source.replace('last = None\n', '''last = None

def project_viewports():
    field = window.project_page.project_name
    label = getattr(field, '_f8_accessible_label', None)
    rows = []
    parent = field.parentWidget()
    while parent is not None:
        if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(field):
            viewport = parent.viewport()
            field_rect = QRect(field.mapTo(viewport, QPoint(0, 0)), field.size())
            label_rect = QRect(label.mapTo(viewport, QPoint(0, 0)), label.size()) if label else QRect()
            rows.append({'scroll': parent.objectName(), 'viewport': list(viewport.rect().getRect()),
                'field': list(field_rect.getRect()), 'label': list(label_rect.getRect()),
                'field_contained': viewport.rect().contains(field_rect),
                'label_contained': viewport.rect().contains(label_rect) if label else None,
                'h': parent.horizontalScrollBar().value(), 'v': parent.verticalScrollBar().value()})
        parent = parent.parentWidget()
    return rows
''')
source=source.replace("'runner_state': str(window.runner._process.state())}",
    "'runner_state': str(window.runner._process.state()),\n"
    "        'edit_history': {'undo': window._edit_session.can_undo, 'redo': window._edit_session.can_redo, 'modified': window._edit_session.is_modified},\n"
    "        'project_viewports': project_viewports() if window.page_stack.currentIndex() == 1 else []}")
assert source != (base/'host.py').read_text(encoding='utf-8')
compile(source,str(base/'host-v2.py'),'exec')
(base/'host-v2.py').write_text(source,encoding='utf-8')
print(base/'host-v2.py')

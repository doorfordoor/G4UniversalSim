from pathlib import Path
import difflib
root=Path.cwd();out=root/'out/collab/f8-project-dock150'
p=root/'gui/g4usim_gui/core/accessibility.py';old=p.read_text(encoding='utf-8-sig');new=old.replace('import re\n','import re\nimport weakref\nfrom shiboken6 import isValid\n').replace('QObject, QPoint, QRect, Qt','QObject, QPoint, QRect, Qt, QTimer')
new=new.replace('        self.owner = owner\n        QApplication', '''        self.owner = owner
        self._pending_focus = None
        self._settle_pass = 0
        self._reveal_closed = False
        self._reveal_timer = QTimer(self)
        self._reveal_timer.setSingleShot(True)
        self._reveal_timer.timeout.connect(self._reveal_after_layout)
        QApplication''')
new=new.replace('    def close(self):\n        QApplication', '''    def close(self):
        self._reveal_closed = True
        self._pending_focus = None
        self._reveal_timer.stop()
        QApplication''')
methods='''    def _queue_focus_reveal(self, widget):
        control = _focus_control(widget)
        if control is not None and not self._reveal_closed:
            self._pending_focus = weakref.ref(control)
            self._settle_pass = 0
            self._reveal_timer.start(0)

    def _reveal_after_layout(self):
        control = self._pending_focus() if self._pending_focus else None
        if (self._reveal_closed or not isValid(self.owner)
                or getattr(self.owner, '_closing', False)
                or control is None or not isValid(control)
                or _focus_control(QApplication.focusWidget()) is not control
                or not owned_widget(self.owner, control)
                or not control.isVisible() or not control.isEnabled()):
            self._pending_focus = None
            return
        # QMainWindow may still have its central page parked at (-500,-500,0,0)
        # during FocusIn. Yield another event-loop turn for its posted relayout.
        if self._settle_pass == 0:
            self._settle_pass = 1
            self._reveal_timer.start(0)
            return
        # Clear before scrolling so our own Move events cannot re-arm this task.
        self._pending_focus = None
        ensure_focus_visible(control)

'''
new=new.replace('    def eventFilter(self, watched, event):  # noqa: N802\n',methods+'''    def eventFilter(self, watched, event):  # noqa: N802
        if isinstance(watched, QWidget) and event.type() == QEvent.FocusIn:
            # A new focus, including a foreign window, supersedes the old task.
            self._pending_focus = None
            self._reveal_timer.stop()
''')
new=new.replace('            ensure_focus_visible(watched)\n', '            ensure_focus_visible(watched)\n            self._queue_focus_reveal(watched)\n')
new=new.replace('        elif event.type() == QEvent.Show and isinstance(watched, QDialog):', '''        elif self._pending_focus and event.type() in (QEvent.LayoutRequest, QEvent.Resize, QEvent.Move):
            control = self._pending_focus()
            if (control is not None and isValid(control)
                    and (watched is control or watched.isAncestorOf(control))):
                self._settle_pass = 0
                self._reveal_timer.start(0)
        elif event.type() == QEvent.Show and isinstance(watched, QDialog):''')
(out/'accessibility.proposed.py').write_text(new,encoding='utf-8')
(out/'accessibility.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/gui/g4usim_gui/core/accessibility.py',tofile='b/gui/g4usim_gui/core/accessibility.py')),encoding='utf-8')
(out/'candidate-debug-subclass.py').write_text((out/'candidate.py').read_text(encoding='utf-8'),encoding='utf-8')
(out/'candidate.py').write_text('''"""OUT-only loader: apply proposed source in memory, leave tracked bytes unchanged."""
from pathlib import Path
import g4usim_gui.core.accessibility as api
def install():
    path=Path(__file__).with_name('accessibility.proposed.py')
    exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),api.__dict__)
''',encoding='utf-8')
p=out/'probe-regression.py';s=p.read_text(encoding='utf-8');s=s.replace("regression'+os.environ", "regression-final'+os.environ");s=s.replace("w.accessibility_controller.reveal_evidence", "getattr(w.accessibility_controller,'reveal_evidence',[])");p.write_text(s,encoding='utf-8')
print('out-only proposal and patch prepared')

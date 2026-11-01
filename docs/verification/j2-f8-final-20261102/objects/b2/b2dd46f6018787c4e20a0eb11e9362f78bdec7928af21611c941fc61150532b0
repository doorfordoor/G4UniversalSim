"""OUT-only candidate; installs a subclass in memory, never edits product sources."""
import weakref
from shiboken6 import isValid
from PySide6.QtCore import QEvent,QTimer
from PySide6.QtWidgets import QApplication,QWidget
import g4usim_gui.core.accessibility as api
BaseController=api.AccessibilityController
class DeferredRevealController(BaseController):
    def __init__(self,owner):
        self._pending_focus=None
        self._settle_pass=0
        self.reveal_evidence=[]
        super().__init__(owner)
        self._reveal_timer=QTimer(self)
        self._reveal_timer.setSingleShot(True)
        self._reveal_timer.timeout.connect(self._reveal_after_layout)
    def close(self):
        self._pending_focus=None
        self._reveal_timer.stop()
        super().close()
    def _arm(self,control):
        self._pending_focus=weakref.ref(control)
        self._settle_pass=0
        self._reveal_timer.start(0)
        self.reveal_evidence.append({'debug':'arm','name':control.accessibleName()})
    def _reveal_after_layout(self):
        control=self._pending_focus() if self._pending_focus else None
        self.reveal_evidence.append({'debug':'flush','pending':repr(control),'focus':repr(QApplication.focusWidget()),'valid_owner':isValid(self.owner)})
        if (not isValid(self.owner) or control is None or not isValid(control)
                or api._focus_control(QApplication.focusWidget()) is not control
                or not api.owned_widget(self.owner,control)
                or not control.isVisible() or not control.isEnabled()):
            self._pending_focus=None
            return
        # Yield a second event-loop turn, so QMainWindow's posted relayout runs
        # after leaving its dock-page zero-size anchor and before mapping focus.
        if self._settle_pass==0:
            self._settle_pass=1
            self._reveal_timer.start(0)
            return
        self._pending_focus=None  # our own minimal scroll must not re-arm itself
        scroll=getattr(self.owner,'content_scroll',None)
        before=scroll.horizontalScrollBar().value() if scroll else None
        api.ensure_focus_visible(control)
        self.reveal_evidence.append({'name':control.accessibleName(),'before_h':before,'after_h':scroll.horizontalScrollBar().value() if scroll else None})
    def eventFilter(self,watched,event):
        result=super().eventFilter(watched,event) # retains synchronous reveal/union
        if not hasattr(self,'_reveal_timer'):
            return result
        if isinstance(watched,QWidget) and event.type()==QEvent.FocusIn:
            # Any new focus, including foreign windows, cancels the old task.
            self._pending_focus=None
            self._reveal_timer.stop()
            if isinstance(watched,QWidget):
                control=api._focus_control(watched)
                if control is not None and api.owned_widget(self.owner,control):self._arm(control)
        elif self._pending_focus and event.type() in (QEvent.LayoutRequest,QEvent.Resize,QEvent.Move):
            control=self._pending_focus()
            if (control is not None and isValid(control) and isinstance(watched,QWidget)
                    and api.owned_widget(self.owner,watched)
                    and (watched is control or watched.isAncestorOf(control))):
                self._settle_pass=0
                self._reveal_timer.start(0)
        return result

def install():
    api.AccessibilityController=DeferredRevealController

# First leave Project naturally and drain that navigation. Merely
# focusing the already-current Project field would queue nothing.
key(window, Qt.Key_1, Qt.ControlModifier | Qt.AltModifier)
controller = window.accessibility_controller
assert window.start_page.isAncestorOf(QApplication.focusWidget())
assert controller._pending_focus is None
# No event processing between these navigations: prove a real old
# Project request exists, then prove Start replaces/cancels it.
window.focus_page(1)
assert QApplication.focusWidget() is field
assert controller._pending_focus is not None
assert controller._pending_focus() is field
assert controller._reveal_timer.isActive()
observations.append({'stage': 'stale-project-queued',
                     'page': window.page_stack.currentIndex(),
                     'pending_is_project': controller._pending_focus() is field,
                     'timer_active': controller._reveal_timer.isActive()})
window.focus_page(0)
newest = QApplication.focusWidget()
assert newest is not field and window.start_page.isAncestorOf(newest)
pending = controller._pending_focus() if controller._pending_focus else None
assert pending is not field
assert pending is None or pending is newest
observations.append({'stage': 'stale-start-supersedes',
                     'page': window.page_stack.currentIndex(),
                     'old_project_pending': pending is field,
                     'pending_is_current_start': pending is newest,
                     'pending_cancelled': pending is None})
settle()
assert controller._pending_focus is None
assert window.page_stack.currentIndex() == 0
assert QApplication.focusWidget() is newest and window.start_page.isAncestorOf(newest)
parent = newest.parentWidget()
while parent is not None:
    if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(newest):
        viewport = parent.viewport()
        target = QRect(newest.mapTo(viewport, QPoint(0, 0)), newest.size())
        if target.width() <= viewport.width() and target.height() <= viewport.height():
            assert viewport.rect().contains(target), (parent.objectName(), target)
    parent = parent.parentWidget()

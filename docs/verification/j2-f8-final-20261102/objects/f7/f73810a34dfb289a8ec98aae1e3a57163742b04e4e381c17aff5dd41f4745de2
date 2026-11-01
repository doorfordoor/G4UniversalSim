def test_retained_dock_focus(app, output=None):
    """Native150 regression: reveal current focus after dock/central relayout.

    Uses production navigation and the real modal wizard, without preparing scroll
    positions. A separate window keeps the pre-existing smoke fixture untouched.
    """
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QVBoxLayout, QStackedWidget
    from shiboken6 import isValid
    from g4usim_gui.core.accessibility import owned_widget
    from g4usim_gui.core.i18n import set_application_language

    def settle():
        # Process posted QMainWindow layouts and queued focus work, never fix
        # geometry or scroll offsets from the test.
        for _ in range(8):
            app.processEvents()
        QTest.qWait(30)

    def key(window, key_code, modifiers=Qt.NoModifier):
        window.activateWindow()
        QTest.qWait(20)
        QTest.keyClick(window, key_code, modifiers)
        settle()

    observations = []
    with tempfile.TemporaryDirectory(prefix='f8-retained-docks-') as temp:
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, temp)
        apply_theme(app, 'light')
        set_application_language(app, 'zh_CN')
        window = MainWindow()
        project = window.project
        project.executable = os.environ.get('G4USIM_EXE', project.executable)
        project.pathSettings.executable = project.executable
        project.runsRoot = str(Path(temp) / 'runs')
        project.pathSettings.runs_root = project.runsRoot
        project.outputDir = str(Path(temp) / 'runs' / 'demo' / 'output')
        window._set_project(project)
        window._reset_edit_history()
        window.config_builder_page._backend_timer.stop()
        window.config_builder_page.schedule_backend_geometry = lambda *args, **kwargs: None
        window.resize(760, 640)
        docks = dict(window.workspace_layout.docks)
        owners = {name: dock.parentWidget() for name, dock in docks.items()}
        before = snapshot_fingerprint(window.capture_workspace())
        history = (window._edit_session.can_undo, window._edit_session.can_redo,
                   window._edit_session.is_modified)
        field = window.project_page.project_name
        label = field._f8_accessible_label
        foreign = None
        owned = None

        def observe(stage):
            settle()
            current = QStackedWidget.currentWidget(window.page_stack)
            ancestors = []
            parent = field.parentWidget()
            while parent is not None:
                if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(field):
                    viewport = parent.viewport()
                    whole = QRect(field.mapTo(viewport, QPoint(0, 0)), field.size())
                    union = whole.united(QRect(label.mapTo(viewport, QPoint(0, 0)), label.size()))
                    ancestors.append({'scroll': parent.objectName(),
                                      'viewport': list(viewport.rect().getRect()),
                                      'field': list(whole.getRect()), 'union': list(union.getRect()),
                                      'field_intersection': list(whole.intersected(viewport.rect()).getRect()),
                                      'h': parent.horizontalScrollBar().value(),
                                      'v': parent.verticalScrollBar().value()})
                parent = parent.parentWidget()
            observations.append({'stage': stage, 'page': window.page_stack.currentIndex(),
                                 'central': list(current.geometry().getRect()),
                                 'focus_is_project_name': QApplication.focusWidget() is field,
                                 'scrolls': ancestors})
            if output:
                output.mkdir(parents=True, exist_ok=True)
                assert window.grab().save(str(output / ('retained-' + stage + '.png')))

        def assert_project_visible():
            assert window.page_stack.currentIndex() == 1
            assert QApplication.focusWidget() is field
            parent = field.parentWidget()
            checked = []
            while parent is not None:
                if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(field):
                    viewport = parent.viewport()
                    whole = QRect(field.mapTo(viewport, QPoint(0, 0)), field.size())
                    assert viewport.rect().contains(whole), (parent.objectName(), whole, viewport.rect())
                    union = whole.united(QRect(label.mapTo(viewport, QPoint(0, 0)), label.size()))
                    if union.width() <= viewport.width():
                        assert union.left() >= 0 and union.right() < viewport.width(), (parent.objectName(), union)
                    if union.height() <= viewport.height():
                        assert union.top() >= 0 and union.bottom() < viewport.height(), (parent.objectName(), union)
                    checked.append(parent)
                parent = parent.parentWidget()
            assert window.content_scroll in checked and window.shell_scroll in checked

        try:
            window.show()
            window.activateWindow()
            settle()
            key(window, Qt.Key_2, Qt.ControlModifier | Qt.AltModifier)
            observe('01-project-initial')
            assert_project_visible()
            key(window, Qt.Key_3, Qt.ControlModifier | Qt.AltModifier)
            observe('02-config')
            assert docks['configuration'].isVisible() and docks['preview'].isVisible()
            key(window, Qt.Key_F6)
            observe('03-f6-preview')
            assert docks['preview'].isAncestorOf(QApplication.focusWidget())

            failures = []
            def cancel_wizard():
                dialog = QApplication.activeModalWidget()
                try:
                    assert isinstance(dialog, NewSimulationWizard), dialog
                    for expected in (1, 2, 3):
                        QTest.keyClick(dialog, Qt.Key_Return)
                        settle()
                        assert dialog.currentId() == expected
                    QTest.keyClick(dialog, Qt.Key_Left, Qt.AltModifier)
                    settle()
                    # Replay native AltLeft; Qt does not bind it to Back on
                    # every platform. Cancellation/retained layout is the contract.
                    QTest.keyClick(dialog, Qt.Key_Escape)
                except BaseException as error:
                    failures.append(error)
                finally:
                    if isinstance(dialog, QDialog) and dialog.isVisible():
                        dialog.reject()
            QTimer.singleShot(100, cancel_wizard)
            key(window, Qt.Key_N, Qt.ControlModifier)
            assert not failures, failures
            assert QApplication.activeModalWidget() is None
            observe('04-wizard-cancel')
            window._theme_actions['dark'].trigger()
            observe('05-dark')
            key(window, Qt.Key_2, Qt.ControlModifier | Qt.AltModifier)
            observe('06-project-return')
            assert_project_visible()
            QTest.qWait(100)
            observe('07-project-settled')
            assert_project_visible()
            assert docks['configuration'].isVisible() and docks['preview'].isVisible()

            for index in range(9):
                key(window, Qt.Key_1 + index, Qt.ControlModifier | Qt.AltModifier)
                assert window.page_stack.currentIndex() == index
                focus = QApplication.focusWidget()
                assert focus is not None and window.page_stack.currentWidget().isAncestorOf(focus)
                key(window, Qt.Key_F6)
                focus = QApplication.focusWidget()
                assert focus is not None and owned_widget(window, focus)
                assert all(window.workspace_layout.docks[name] is dock and dock.parentWidget() is owners[name]
                           for name, dock in docks.items())
            key(window, Qt.Key_2, Qt.ControlModifier | Qt.AltModifier)
            observe('08-ninepage-return')
            assert_project_visible()

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

            # A foreign QWidget focus cancels old owned work without panning the
            # main viewport or editing the foreign control.
            foreign = QDialog()
            foreign_field = QLineEdit()
            QVBoxLayout(foreign).addWidget(foreign_field)
            window.focus_page(1)
            offset = window.content_scroll.horizontalScrollBar().value()
            foreign.show()
            foreign.activateWindow()
            foreign_field.setFocus()
            settle()
            assert QApplication.focusWidget() is foreign_field
            assert not owned_widget(window, foreign_field)
            assert window.content_scroll.horizontalScrollBar().value() == offset
            assert foreign_field.text() == ''
            foreign.close()
            foreign.deleteLater()
            foreign = None
            window.activateWindow()
            settle()

            # Destroy an owned focus target with queued work outstanding. The
            # invalid C++ wrapper must never be dereferenced by the callback.
            owned = QDialog(window)
            doomed = QLineEdit()
            QVBoxLayout(owned).addWidget(doomed)
            owned.show()
            owned.activateWindow()
            settle()
            doomed.clearFocus()
            doomed.setFocus()
            assert QApplication.focusWidget() is doomed
            owned.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            assert not isValid(doomed)
            owned = None
            settle()
            key(window, Qt.Key_2, Qt.ControlModifier | Qt.AltModifier)
            assert_project_visible()
            assert snapshot_fingerprint(window.capture_workspace()) == before
            assert (window._edit_session.can_undo, window._edit_session.can_redo,
                    window._edit_session.is_modified) == history
        finally:
            if output:
                output.mkdir(parents=True, exist_ok=True)
                (output / 'retained-dock-focus.json').write_text(
                    json.dumps(observations, ensure_ascii=False, indent=2), encoding='utf-8')
            if foreign is not None and isValid(foreign):
                foreign.close()
                foreign.deleteLater()
            if owned is not None and isValid(owned):
                owned.reject()
                owned.deleteLater()
            close_window(app, window)



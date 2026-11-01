import os,sys,json,tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path.insert(0,str(Path('gui').resolve()));sys.path.insert(0,str(Path('gui/smoke_tests').resolve()))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from smoke_f4_layout import reach,target_visible_through_ancestors
app=QApplication([]);QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,tempfile.mkdtemp(prefix='f8-f4-diag-'))
w=MainWindow();w.config_builder_page._backend_timer.stop();w.config_builder_page.schedule_backend_geometry=lambda *a,**k:None
w.show();app.processEvents();w.project_page.executable.setText('');w._validate_project_diagnostics();w._set_language('en',persist=False);w._set_theme('light');w.resize(1280,768);app.processEvents()
p=w.project_page;r=w.run_page
w.page_stack.setCurrentWidget(p);app.processEvents()
for c in (p.executable,p.diagnostics_panel.table,p.diagnostics_panel.locate_button):reach(app,p.content_scroll,c)
w.page_stack.setCurrentWidget(r);app.processEvents()
for c in (r.command_preview,r.build_button,r.save_logs_button,r.diagnostics_panel.table,r.diagnostics_panel.locate_button):reach(app,r.content_scroll,c)
for key,widget in [('window',w),('outer',w.content_scroll),('outerViewport',w.content_scroll.viewport()),('outerContent',w.content_scroll.widget()),('host',w.workspace_layout.hosts['workspace']),('stack',w.page_stack),('run',r),('logDock',w.workspace_layout.docks['logs']),('stdout',r.stdout_view)]:
 print(key,'size',widget.size().toTuple(),'min',widget.minimumSize().toTuple(),'minHint',widget.minimumSizeHint().toTuple(),'hint',widget.sizeHint().toTuple())
print('stacklayout',w.page_stack.layout().minimumSize().toTuple())
for widget,title,*_ in w._page_specs:print('page',title,'min',widget.minimumSize().toTuple(),'minHint',widget.minimumSizeHint().toTuple())
print('scroll ranges',w.content_scroll.horizontalScrollBar().maximum(),w.content_scroll.verticalScrollBar().maximum())
try:target_visible_through_ancestors(r.stdout_view,r.stdout_view.rect(),full_cell=False)
except AssertionError as e:print('clip',str(e))
close_window(app,w)

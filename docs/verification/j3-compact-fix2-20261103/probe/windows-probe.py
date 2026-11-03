import tempfile
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication,QPushButton
from gui_test_window import MainWindow
app=QApplication([]); t=tempfile.TemporaryDirectory()
app.setOrganizationName("J3IndependentTest");app.setApplicationName("review")
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,t.name)
w=MainWindow()
def size(x,y):
 w.resize(x,y);app.processEvents();app.processEvents()
def log(label): print(label,w.width(),w.height(),a.isHidden(),p.isHidden(),flush=True)
a=w.workspace_layout.docks["ai"];p=w.workspace_layout.docks["preview"]
size(1200,800);w.show();app.processEvents()
if a.isHidden(): a.toggleViewAction().trigger()
if p.isHidden(): p.toggleViewAction().trigger()
app.processEvents();log("menu-open");size(1205,800);log("menu-resize");assert not a.isHidden() and not p.isHidden()
a.setFloating(True);app.processEvents();size(1210,805);log("float-resize"); assert not a.isHidden();a.setFloating(False)
size(1420,805);log("wide");assert not a.isHidden() and not p.isHidden()
w.workspace_layout.apply_preset("configuration");w.page_stack.setCurrentIndex(w.page_stack.indexOf(w.config_builder_page))
size(1200,800)
c=w.config_builder_page;c.workspace_tabs.setCurrentIndex(c.preview3d_tab_index());app.processEvents()
b=next(x for x in w.findChildren(QPushButton) if x.property("workspaceText")=="Show 3D view")
print('button visible/enabled',b.isVisible(),b.isEnabled(),flush=True)
b.click();app.processEvents();log("button-open"); assert not p.isHidden()
size(1205,800);log("button-resize")
a.toggleViewAction().trigger() if a.isHidden() else None
app.processEvents();w.workspace_layout.save(); log("saved")
a.toggleViewAction().trigger();app.processEvents();w.workspace_layout.restore();app.processEvents();log("restored");size(1211,805);log("restored-resize")
w.close();app.processEvents()


from pathlib import Path
import os,sys,json,ast,hashlib,subprocess,traceback
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;OWNER=ROOT/'out/collab/f8-layout-item-compat'
os.environ.update(QT_QPA_PLATFORM='offscreen',PYTHONDONTWRITEBYTECODE='1');sys.path.insert(0,str(ROOT/'gui'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
raw=ROOT/'gui/g4usim_gui/core/accessibility.py';proposed=OWNER/'accessibility.proposed.py'
assert sha(proposed)=='c9d87e23c88704fedc2c17a8a954aba9acf365c607ea47fe86b6c56854be2be7'
assert sha(OWNER/'accessibility.patch')=='697cbc1f7d615bfaf1e2a1448095aa2dd49e8077861497b0d2f0c7ae8a33c7d2'
before=sha(raw)
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QFormLayout,QLabel,QLineEdit,QSpacerItem,QSizePolicy,QLayout
from PySide6.QtCore import QCoreApplication,QEvent
import g4usim_gui.core.accessibility as api
mode=sys.argv[1]
if mode=='candidate':exec(compile(proposed.read_text(encoding='utf-8'),str(proposed),'exec'),api.__dict__)
from g4usim_gui.core.i18n import set_application_language,apply_language,ui_text
from g4usim_gui.widgets.start_page import StartPage
app=QApplication([]);app.setStyle('Fusion')
rows=[]
def destroy(widget):widget.close();widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
def stock():
 root=QWidget();outer=QVBoxLayout(root);form=QFormLayout();box=QHBoxLayout();box.addSpacing(11);a=QLineEdit('keep input');box.addWidget(a);box.addStretch();lab=QLabel('Search');form.addRow(lab,box);outer.addLayout(form)
 grid=QGridLayout();label=QLabel('Runs root');nested=QVBoxLayout();b=QLineEdit('keep root');nested.addStretch();nested.addWidget(b);grid.addWidget(label,0,0);grid.addLayout(nested,0,1);emptylabel=QLabel('Status');empty=QSpacerItem(13,17);grid.addWidget(emptylabel,1,0);grid.addItem(empty,1,1);outer.addLayout(grid);outer.addStretch()
 try:
  for language in ['en','zh_CN','en']:
   set_application_language(app,language);apply_language(root,language);api.decorate_accessibility(root)
   assert lab.buddy() is a and label.buddy() is b
   assert a.accessibleName()==ui_text('Search') and b.accessibleName()==ui_text('Runs root')
   assert api._item_field(empty) is None and emptylabel.buddy() is None
   assert (a.text(),b.text())==('keep input','keep root')
  rows.append('stock nested Form/Grid/HBox/VBox/stretch en/zh/en')
 finally:destroy(root)
def replay(boundary):
 root=QWidget();outer=QVBoxLayout(root);spacer=QSpacerItem(19,23,QSizePolicy.Minimum,QSizePolicy.Expanding);outer.addItem(spacer)
 # Every target remains a real Qt C++ instance. Only provider return value is controlled.
 if boundary=='root':root.layout=lambda:spacer
 else:spacer.layout=lambda:spacer
 try:
  assert isinstance(spacer,QSpacerItem) and not isinstance(spacer,QLayout)
  if boundary=='item':assert api._item_field(spacer) is None
  else:api.decorate_accessibility(root)
  rows.append('controlled non-QLayout '+boundary+' skipped')
 finally:
  if boundary=='root':del root.layout
  else:del spacer.layout
  destroy(root)
stock()
if mode.startswith('frozen-'):
 replay(mode.removeprefix('frozen-'))
 assert False,'frozen boundary unexpectedly accepted controlled provider'
for boundary in ['item','root','child']:replay(boundary)
start=StartPage();start.show()
try:
 for width in [1200,760,1024]:
  start.resize(width,640);start.adapt_to_width(width);app.processEvents()
  for language in ['zh_CN','en','zh_CN']:
   set_application_language(app,language);apply_language(start,language);api.decorate_accessibility(start)
   assert all(b.accessibleName() for b in start.start_actions)
 rows.append('stock real StartPage resize/language')
finally:destroy(start)
oldtree=ast.parse(raw.read_text(encoding='utf-8'));newtree=ast.parse(proposed.read_text(encoding='utf-8'))
find=lambda tree,name:next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
for name in ['_focus_control','focus_first','_reading_anchor','_reveal_axis','ensure_focus_visible','AccessibilityController']:
 assert ast.dump(find(oldtree,name),include_attributes=False)==ast.dump(find(newtree,name),include_attributes=False)
old=ast.parse((ROOT/'gui/smoke_tests/smoke_f8_accessibility.py').read_text(encoding='utf-8'));new=ast.parse((OWNER/'smoke_f8_accessibility.proposed.py').read_text(encoding='utf-8'))
a={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)};b={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
for name in a.keys()-{'main'}:assert ast.dump(a[name],include_attributes=False)==ast.dump(b[name],include_attributes=False)
assert ast.unparse(b['main'].body[-2])=='test_layout_item_compatibility(app)';del b['main'].body[-2];assert ast.dump(a['main'],include_attributes=False)==ast.dump(b['main'],include_attributes=False)
r=subprocess.run(['git','apply','--check',str(OWNER/'accessibility.patch'),str(OWNER/'smoke_f8_accessibility.patch')],cwd=ROOT,capture_output=True,text=True);assert r.returncode==0,r.stderr
assert sha(raw)==before
result={'passed':True,'mode':mode,'groups':rows,'candidate_sha256':sha(proposed),'frozen_sha256':before,'tracked_unchanged':True,'old_focus_union_controller_AST_unchanged':True,'old_smoke_functions_AST_unchanged':True,'main_only_appends':True,'patches_check_exit':0,'controlled_replay_not_natural_CI':True,'RuntimeWarning_not_suppressed':True,'no_native_backend_or_build':True}
(OUT/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

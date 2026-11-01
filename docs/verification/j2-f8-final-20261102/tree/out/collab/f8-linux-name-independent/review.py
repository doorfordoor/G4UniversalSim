from pathlib import Path
import ast,json,hashlib,os,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;OWNER=ROOT/'out/collab/f8-linux-qt-name-18c5858';C=OWNER/'candidate-test-only'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
candidate=C/'smoke_f8_accessibility.proposed.py';old=ROOT/'gui/smoke_tests/smoke_f8_accessibility.py'
assert sha(candidate)=='5f234e69c00d602039cb8f2ebc7daadb4f69edc860e6010989628d06253b3814'
assert sha(C/'fix.patch')=='09409fa22593aceef84bcbcbed5a232c3eae0b0a6225c328a8ba0ec07c65815b'
a=ast.parse(old.read_text(encoding='utf-8'));b=ast.parse(candidate.read_text(encoding='utf-8'))
functions=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
fa,fb=functions(a),functions(b)
assert fb.keys()-fa.keys()=={'_assert_history_provider'}
for name in fa.keys()-{'test_history_directory_accessibility'}:
 assert ast.dump(fa[name],include_attributes=False)==ast.dump(fb[name],include_attributes=False),name
before=sha(old)
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path.insert(0,str(ROOT/'gui'))
import PySide6
if sys.platform.startswith('linux'):os.environ['QT_PLUGIN_PATH']=str(Path(PySide6.__file__).parent/'Qt/plugins')
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtCore import QCoreApplication,QEvent,QLibraryInfo
from PySide6.QtGui import QAccessible
from g4usim_gui.widgets.run_history_page import RunHistoryPage
from g4usim_gui.core.accessibility import decorate_accessibility
from g4usim_gui.core.i18n import set_application_language,apply_language,ui_text
namespace={'sys':sys};exec(compile(ast.Module(body=[fb['_assert_history_provider']],type_ignores=[]),'<exact-candidate-helper>','exec'),namespace)
check=namespace['_assert_history_provider']
app=QApplication([]);app.setStyle('Fusion');page=RunHistoryPage();page.show();app.processEvents()
rows=[];negative=[]
try:
 for language in ['en','zh_CN','en']:
  set_application_language(app,language);apply_language(page,language);decorate_accessibility(page);app.processEvents()
  for name,source in [('runs_root','Runs root'),('search','Search'),('status_filter','Status')]:
   control=getattr(page,name);label=control._f8_accessible_label;interface=QAccessible.queryAccessibleInterface(control)
   assert control.accessibleName()==label.text()==ui_text(source) and label.buddy() is control
   evidence=check(interface,control,label,ui_text(source))
   rows.append({'language':language,'control':name,'property':control.accessibleName(),'name':interface.text(QAccessible.Name),'value':interface.text(QAccessible.Value),'currentText':control.currentText() if name=='status_filter' else None,'role':str(interface.role()),**evidence})
  control=page.status_filter;label=control._f8_accessible_label;expected=ui_text('Status')
  label.setBuddy(None)
  try:
   assert control.accessibleName()==expected
   interface=QAccessible.queryAccessibleInterface(control)
   assert not any(t.object() is label for t,f in interface.relations(QAccessible.Label) if f & QAccessible.Label)
   try:check(interface,control,label,expected)
   except AssertionError:negative.append({'language':language,'case':'missing_actual_buddy_with_correct_property','rejected':True})
   else:assert False,'missing real Label passed'
  finally:label.setBuddy(control)
  check(QAccessible.queryAccessibleInterface(control),control,label,expected)
  impostor=QLabel(expected,page)
  try:
   try:check(QAccessible.queryAccessibleInterface(control),control,impostor,expected)
   except AssertionError:negative.append({'language':language,'case':'same_text_wrong_real_label_object','rejected':True})
   else:assert False,'wrong label object passed'
  finally:impostor.deleteLater()
  try:check(QAccessible.queryAccessibleInterface(page.search),control,label,expected)
  except AssertionError:negative.append({'language':language,'case':'wrong_interface_object','rejected':True})
  else:assert False,'wrong interface object passed'
 # Real Linux/Windows provider with a second selection and empty current value.
 for index in [5,-1,0]:
  page.status_filter.setCurrentIndex(index);app.processEvents();control=page.status_filter;label=control._f8_accessible_label
  interface=QAccessible.queryAccessibleInterface(control);check(interface,control,label,ui_text('Status'))
  rows.append({'case':'actual_combo_selection','index':index,'currentText':control.currentText(),'name':interface.text(QAccessible.Name),'value':interface.text(QAccessible.Value)})
finally:
 page.close();page.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
assert sha(old)==before
result={'passed':True,'runtime':{'platform':sys.platform,'python':sys.executable,'pyside':PySide6.__version__,'qt':QLibraryInfo.version().toString()},'candidate_sha256':sha(candidate),'old_functions_except_target_and_main_AST_unchanged':True,'no_Name_provider_override_or_platform_faking':True,'rows':rows,'negative':negative,'tracked_unchanged':True,'scope':'actual micro Qt provider helper only; not full655/native/profile/backend/CI acceptance'}
name='linux' if sys.platform.startswith('linux') else 'windows'
(OUT/(name+'-receipt.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))

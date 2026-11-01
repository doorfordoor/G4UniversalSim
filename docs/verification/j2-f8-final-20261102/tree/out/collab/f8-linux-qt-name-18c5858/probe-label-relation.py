import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path.insert(0,str(ROOT/'gui'))
import PySide6,shiboken6
if sys.platform!='win32':os.environ['QT_PLUGIN_PATH']=str(Path(PySide6.__file__).parent/'Qt/plugins')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QLocale
from PySide6.QtGui import QAccessible
from g4usim_gui.widgets.run_history_page import RunHistoryPage
from g4usim_gui.core.i18n import apply_language,set_application_language,ui_text
from g4usim_gui.core.accessibility import decorate_accessibility
app=QApplication([]);app.setStyle('Fusion');page=RunHistoryPage();page.resize(800,600);page.show();app.processEvents()
top=page.layout().itemAt(0).layout();filters=page.layout().itemAt(1).layout();pairs=[(top.itemAt(0).widget(),page.runs_root,'Runs root'),(filters.itemAt(0).widget(),page.search,'Search'),(filters.itemAt(2).widget(),page.status_filter,'Status')]
rows=[]
for lang in ['en','zh_CN','en']:
 set_application_language(app,lang);apply_language(page,lang);decorate_accessibility(page);app.processEvents()
 for label,control,source in pairs:
  interface=QAccessible.queryAccessibleInterface(control);obj=interface.object();actual=interface.text(QAccessible.Name)
  rows.append({'language':lang,'source':source,'label':label.text(),'buddy':label.buddy() is control,'property':control.accessibleName(),'expected':ui_text(source),'actual':actual,'value':interface.text(QAccessible.Value),'current_text':control.currentText() if hasattr(control,'currentText') else None,'relations':[{'name':target.text(QAccessible.Name),'role':str(target.role()),'is_label':target.object() is label,'flags':str(flags)}for target,flags in interface.relations(QAccessible.Label)],'actual_codepoints':[hex(ord(c))for c in actual],'role':str(interface.role()),'interface_object_class':type(obj).__name__,'interface_object_is_control':obj is control,'control_pointer':shiboken6.getCppPointer(control)[0],'object_pointer':shiboken6.getCppPointer(obj)[0] if obj else None})
result={'runtime':{'python':sys.version,'executable':sys.executable,'pyside':PySide6.__version__,'locale':QLocale().name(),'qpa':app.platformName()},'rows':rows}
(OUT/(sys.argv[1]+'.json')).write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8'))
for row in rows:print(row['language'],row['source'],'property',repr(row['property']),'actual',repr(row['actual']),'object_same',row['interface_object_is_control'],row['role'],'relations',row['relations'],flush=True)
page.close()

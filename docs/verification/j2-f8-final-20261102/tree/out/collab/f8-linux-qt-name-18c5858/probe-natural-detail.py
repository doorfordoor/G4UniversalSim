import os,sys,json,ast,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
import PySide6
from PySide6.QtCore import qVersion,QLocale
os.environ['QT_PLUGIN_PATH']=str(Path(PySide6.__file__).parent/'Qt/plugins')
original=ROOT/'gui/smoke_tests/smoke_f8_accessibility.py'
source=original.read_text(encoding='utf-8-sig')
needle='                    assert interface.text(QAccessible.Name) == ui_text(source)'
assert source.count(needle)==1
injected=source.replace(needle,'                    __record_name(control, language, source, interface)\n'+needle)
rows=[]
def record(control,language,source,interface):
 from PySide6.QtGui import QAccessible
 from PySide6.QtWidgets import QApplication
 from g4usim_gui.core.i18n import ui_text
 label=getattr(control,'_f8_accessible_label',None)
 row={'class':type(control).__name__,'language':language,'source':source,'property':control.accessibleName(),'interface_name':interface.text(QAccessible.Name),'expected':ui_text(source),'role':str(interface.role()),'label':label.text() if label else None,'buddy':bool(label and label.buddy() is control),'object_same':interface.object() is control,'runtime':{'python':sys.version,'executable':sys.executable,'pyside':PySide6.__version__,'qt':qVersion(),'locale':QLocale().name(),'qpa':QApplication.platformName()}}
 rows.append(row);print('NATURAL_ACCESSIBLE_NAME='+json.dumps(row,ensure_ascii=False),flush=True)
namespace={'__name__':'__main__','__file__':str(original),'__record_name':record}
sys.argv=[str(original),'--output',str(OUT/'linux-natural-detail')]
try:exec(compile(injected,str(original),'exec'),namespace)
finally:(OUT/'linux-natural-detail.json').write_bytes(json.dumps({'original_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'diagnostic_change':'one read-only print call before original unchanged assert; original __file__ and ROOT','rows':rows},ensure_ascii=False,indent=2).encode('utf-8'))

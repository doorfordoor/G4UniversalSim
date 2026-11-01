import os,sys,json
from pathlib import Path
root=Path.cwd();out=root/'out/collab/f8-history-label/v2'
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path.insert(0,str(root/'gui'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QAccessible
from g4usim_gui.widgets.run_history_page import RunHistoryPage
app=QApplication([]);page=RunHistoryPage();top=page.layout().itemAt(0).layout();filters=page.layout().itemAt(1).layout()
pairs=[(top.itemAt(0).widget(),page.runs_root,'Runs root'),(filters.itemAt(0).widget(),page.search,'Search'),(filters.itemAt(2).widget(),page.status_filter,'Status')]
rows=[]
for label,control,source in pairs:
 interface=QAccessible.queryAccessibleInterface(control);rows.append({'source':source,'accessible_name':control.accessibleName(),'qt_name':interface.text(QAccessible.Name),'buddy':label.buddy() is control})
(out/'frozen-negative.json').write_bytes(json.dumps(rows,indent=2).encode('utf-8'));print(json.dumps(rows),flush=True)
assert all(row['buddy'] and row['qt_name']==row['source'] for row in rows),'frozen product lacks History label/name binding'

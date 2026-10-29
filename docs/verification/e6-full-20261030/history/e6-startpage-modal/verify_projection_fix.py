"""Re-run the unchanged original integer probe, recording expected rejection boxes."""
from pathlib import Path
import json
import os
import runpy
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QMessageBox
WORK=Path(__file__).resolve().parent
source=WORK/'review_large_integers.py'
raw=source.read_bytes()
old=WORK/'large-integers.json'
before=WORK/'large-integers-before-fix.json'
if not before.exists():before.write_bytes(old.read_bytes())
boxes=[]
with patch.object(QMessageBox,'critical',staticmethod(lambda _p,title,message,*_a: boxes.append({'title':title,'message':str(message)}))):
    runpy.run_path(str(source),run_name='__main__')
assert source.read_bytes()==raw
data=json.loads(old.read_text(encoding='utf-8'))
assert len(boxes)==len(data['facts'])==11
for name,fact in data['facts'].items():
    assert fact['model_load_accepted'] is True,name
    assert fact['helper_return'] is False,name
    assert fact['old_project_object_retained'] is True,name
    assert fact['project_page_building'] is False and fact['config_page_building'] is False,name
    assert fact['generated_package_stale'] is False and fact['generated_package_dir']=='sentinel-package',name
    assert fact['source_unchanged'] is True,name
assert all(box['title']=='Open project failed' for box in boxes)
(WORK/'projection-fix-boxes.json').write_text(json.dumps(boxes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Original 11 integer fixtures now reject before publication; old model, paths and GUI flags preserved.')

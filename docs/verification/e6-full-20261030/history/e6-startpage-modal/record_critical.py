"""Replay an unchanged smoke copy, recording only its unexpected modal critical."""
from pathlib import Path
import hashlib
import json
import os
import traceback
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QMessageBox

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
SOURCE=ROOT/'gui/smoke_tests/smoke_start_page.py'
raw=SOURCE.read_bytes()
COPY=WORK/'smoke_start_page.unmodified.py'
COPY.write_bytes(raw)
records=[]

def record(*args,**kwargs):
    records.append({'title':str(args[1]) if len(args)>1 else '',
                    'message':str(args[2]) if len(args)>2 else '',
                    'stack':[f'{f.filename}:{f.lineno}:{f.name}' for f in traceback.extract_stack()[-7:-1]]})
    return QMessageBox.StandardButton.Ok

try:
    # Keep __file__ and compiled filename equal to the original so its unchanged
    # GUI = parents[1] and bundled-gallery paths resolve exactly as in the run.
    with patch.object(QMessageBox,'critical',staticmethod(record)):
        exec(compile(COPY.read_bytes(),str(SOURCE),'exec'),{'__name__':'__main__','__file__':str(SOURCE)})
    assert len(records)==1,records
    assert 'demo_project.json' in records[0]['message'],records
finally:
    unchanged=SOURCE.read_bytes()==raw
    result={'original_sha256':hashlib.sha256(raw).hexdigest(),
            'copy_sha256':hashlib.sha256(COPY.read_bytes()).hexdigest(),
            'frozen_source_unchanged':unchanged,'critical_calls':records}
    (WORK/'critical-record.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert unchanged
print('Unchanged smoke replay finished; one unexpected critical recorded non-modally.')

"""Capture the duplicate-and-run command without starting any backend process."""
from pathlib import Path
import json
import os
import sys
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM']='offscreen'
ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'gui'))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.history import run_history_store
from g4usim_gui.history.run_package_actions import _ini_entries
from g4usim_gui.main_window import MainWindow
from g4usim_gui.models.package_model import GeometrySettings,PathSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.writers.package_writer import create_run_package

app=QApplication([])
app.setOrganizationName('G4USimReview')
app.setApplicationName('E6DuplicateCLI')
app.setQuitOnLastWindowClosed(False)
run_history_store.STATE_PATH=WORK/'state.json'
runs=WORK/'runs'
runs.mkdir(exist_ok=True)
material=ROOT/'config/materials/material.ini'
geometry=ROOT/'config/geometry/simple_box.ini'
paths=PathSettings(executable=sys.executable,workspace_root=str(ROOT),runs_root=str(runs),
                   materials_config=str(material),geometry_config=str(geometry))
project=G4USimProject(projectName='writer_run',executable=sys.executable,workspaceRoot=str(ROOT),runsRoot=str(runs))
package,_=create_run_package(project=project,paths=paths,
                            run=RunSettings(run_name='writer_run',threads=2,seed=43,beam_on=2),
                            geometry=GeometrySettings(template='simple_box',config_path=str(geometry)),
                            source=SourceSettings(),physics=PhysicsSettings(),scoring=ScoringSettings())
window=MainWindow()
for timer in window.findChildren(QTimer):timer.stop()
window.project.executable=sys.executable
window.project.runsRoot=str(runs)
window.project.threads=7
window.project.seed='999'
window.project.runName='unrelated_current_run'
window.project.runSettings.threads=7
window.project.runSettings.seed=999
window.project.runSettings.run_name='unrelated_current_run'
window._set_project(window.project)
captured=[]
def capture_inspection(*,run_after=False):
    captured.append({'run_after':run_after,'command':window.runner.build_command(window.project)})
with patch.object(window,'inspect_external_macro',side_effect=capture_inspection):
    window.duplicate_history_package(package.package_dir,run_after=True)
assert len(captured)==1,captured
command=captured[0]['command']
main=Path(window.project.configPath)
fields={identity:value for identity,value,*_ in _ini_entries(main.read_bytes(),'duplicate main')[1]}
snapshot=json.loads(Path(package.project_snapshot_path).read_text(encoding='utf-8'))
result={'source_package':package.package_dir,'duplicate_main':str(main),
        'writer_main':{'threads':fields['run','threads'],'seed':fields['run','seed'],'name':fields['run','name']},
        'old_snapshot_flat':{k:snapshot[k] for k in ('threads','seed','runName')},
        'captured_before_backend_inspection':captured[0],
        'backend_started':window.runner.is_running(),'inspection_process_started':window._macro_inspection.state().name}
assert result['writer_main']=={'threads':'2','seed':'43','name':'writer_run'}
assert command[command.index('--threads')+1]=='7'
assert command[command.index('--seed')+1]=='999'
assert command[command.index('--run-name')+1]=='unrelated_current_run'
assert not window.runner.is_running()
(WORK/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
window.close()
window.deleteLater()
app.processEvents()

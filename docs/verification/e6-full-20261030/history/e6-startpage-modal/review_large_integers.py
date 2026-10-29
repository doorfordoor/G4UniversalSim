"""Read-only product probe: model-accepted integers and transactional GUI import."""
from pathlib import Path
import hashlib
import json
import os
import sys
import traceback

os.environ['QT_QPA_PLATFORM']='offscreen'
ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'gui'))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.project import load_project
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow

app=QApplication([])
app.setOrganizationName('G4USimIndependentReview')
app.setApplicationName('E6LargeIntegerImport')
app.setQuitOnLastWindowClosed(False)
run_history_store.STATE_PATH=WORK/'large-int-state.json'
files=['gui/g4usim_gui/window/project.py','gui/g4usim_gui/widgets/project_page.py',
       'gui/g4usim_gui/core/project.py','gui/g4usim_gui/widgets/config_builder_page.py']
hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
cases={
 'flat_threads_huge':{'threads':10**100},
 'run_threads_huge':{'runSettings':{'threads':10**100}},
 'events_huge':{'runSettings':{'beam_on':10**100}},
 'settings_hist_bins_huge':{'scoringSettings':{'hist_bins':10**100}},
 'editor_hist_bins_huge':{'scoringEditor':{'hist_bins':10**100}},
 'preview_rays_huge':{'sourceEditor':{'preview_ray_count':10**100}},
 'preview_seed_huge':{'sourceEditor':{'random_seed_preview':10**100}},
 'trajectories_huge':{'scoringEditor':{'trajectory_events':10**100}},
 'flat_threads_clamped':{'threads':2048},
 'events_clamped':{'runSettings':{'beam_on':2000000001}},
 'hist_bins_clamped':{'scoringEditor':{'hist_bins':10000001}},
}
facts={}
for name,extra in cases.items():
    source=WORK/f'{name}.json'
    source.write_text(json.dumps({'projectName':'incoming-'+name,**extra}),encoding='utf-8')
    source_before=source.read_bytes()
    candidate=load_project(source)
    window=MainWindow()
    for timer in window.findChildren(QTimer):timer.stop()
    old=window.project
    window.project_file=WORK/'old-current.json'
    window._generated_package_stale=False
    window._generated_package_dir='sentinel-package'
    old_name=window.project_page.project_name.text()
    fact={'model_load_accepted':True,'old_name':old_name}
    try:
        fact['helper_return']=window._load_project_path(str(source))
    except Exception as error:
        fact['exception_type']=type(error).__name__
        fact['exception']=str(error)
        fact['traceback']=traceback.format_exc()
    fact.update({'old_project_object_retained':window.project is old,
                 'current_project_name':window.project.projectName,
                 'project_file':str(window.project_file),
                 'project_page_name':window.project_page.project_name.text(),
                 'project_page_building':window.project_page._building,
                 'config_page_building':window.config_builder_page._building,
                 'generated_package_stale':window._generated_package_stale,
                 'generated_package_dir':window._generated_package_dir,
                 'model_threads':window.project.threads,
                 'view_threads':window.project_page.threads.value(),
                 'model_beam_on':window.project.runSettings.beam_on,
                 'view_beam_on':window.config_builder_page.beam_on.value(),
                 'model_editor_bins':window.project.scoringEditor.hist_bins,
                 'view_editor_bins':window.config_builder_page.scoring_editor_bins.value(),
                 'source_unchanged':source.read_bytes()==source_before})
    facts[name]=fact
    window.close()
    window.deleteLater()
assert all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==value for f,value in hashes.items())
(WORK/'large-integers.json').write_text(json.dumps({'product_hashes':hashes,'facts':facts},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({name:{k:fact[k] for k in ('model_load_accepted','old_project_object_retained','project_page_building','config_page_building','generated_package_stale','generated_package_dir','helper_return','exception_type') if k in fact} for name,fact in facts.items()},ensure_ascii=False,indent=2))

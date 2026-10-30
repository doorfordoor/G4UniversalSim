import json,os,sys,tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'gui'))
from PySide6.QtWidgets import QApplication,QWidget
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot,project_for_snapshot
from g4usim_gui.core.project import G4USimProject,project_to_dict
from g4usim_gui.editors.material_editor_model import MaterialDocument
from g4usim_gui.core.workspace_recovery import RecoveryStore
from g4usim_gui.window.recovery import RecoveryController

def payload(name):
 p=G4USimProject(projectName=name);p.materialEditor=MaterialDocument()
 return project_to_dict(project_for_snapshot(WorkspaceSnapshot(p)))
def denies(action):
 try:action()
 except ValueError:return True
 return False
app=QApplication.instance() or QApplication([]);owner=QWidget();facts={}
with tempfile.TemporaryDirectory(prefix='f5-recovery-independent-fixed-') as directory:
 root=Path(directory);s=RecoveryStore(root/'store').open_session();a=payload('one');b=payload('two')
 s.publish(a,4);before=s.path.read_bytes()
 assert denies(lambda:s.publish(b,4)) and s.path.read_bytes()==before
 s.publish(a,4);assert s.path.read_bytes()==before
 s.retire('discarded');assert denies(lambda:s.publish(a,4)) and not s.path.exists()
 s.publish(b,5);assert json.loads(s.path.read_bytes())['revision']==5;s.close()
 facts['store_same_revision_conflict_rejected']=True;facts['store_duplicate_idempotent']=True;facts['retired_replay_rejected_new_revision_allowed']=True
 c=RecoveryController(owner,restore=lambda p:True,root=root/'controller')
 c.changed(b,2);assert denies(lambda:c.changed(a,1));assert denies(lambda:c.changed(a,2));c.changed(b,2);assert c.flush()
 data=json.loads(c.session.path.read_bytes());assert data['revision']==2 and data['payload']['projectName']=='two'
 assert c.saved();assert denies(lambda:c.changed(b,2));c.changed(a,3);assert c.flush()
 assert json.loads(c.session.path.read_bytes())['revision']==3
 facts['controller_older_and_conflicting_notification_rejected']=True;facts['newer_pending_preserved']=True;facts['controller_retired_replay_rejected']=True
 assert c.close(keep=True);app.processEvents()
owner.close();facts['scope']='independent public API rechecks, not a claim about ordinary mouse reachability'
p=ROOT/'out/collab/f5-recovery-r1-independent-fixed.json'
with p.open('x',encoding='utf-8') as h:json.dump(facts,h,indent=2)
print(json.dumps(facts))

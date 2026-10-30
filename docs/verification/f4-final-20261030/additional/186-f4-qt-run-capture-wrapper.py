"""Read-only signal observation of real runner output; target source unchanged."""
from pathlib import Path
import os,sys,runpy,json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gui'))
from g4usim_gui.core.runner import G4USimRunner
OUT=Path(os.environ['G4_F4_QA_STATE_ROOT']);OUT.mkdir(parents=True,exist_ok=True)
original=G4USimRunner.__init__
def emit(kind,text):
    with (OUT/'runner-signal-capture.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps({'kind':kind,'text':text},ensure_ascii=False,default=str)+'\n')
def init(self,*args,**kwargs):
    original(self,*args,**kwargs)
    self.stderrReceived.connect(lambda text:emit('stderr',text))
    self.stdoutReceived.connect(lambda text:emit('stdout',text))
    self.errorOccurred.connect(lambda text:emit('error',text))
G4USimRunner.__init__=init
sys.argv=[str(ROOT/'out/collab/f4-qt-test-wrapper.py'),*sys.argv[1:]]
runpy.run_path(sys.argv[0],run_name='__main__')

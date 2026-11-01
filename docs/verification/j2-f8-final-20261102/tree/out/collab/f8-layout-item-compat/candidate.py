from pathlib import Path
import g4usim_gui.core.accessibility as module
def install():
    path=Path(__file__).with_name('accessibility.proposed.py')
    exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),module.__dict__)

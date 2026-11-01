"""Load only the History label proposal in memory; do not touch tracked code."""
from pathlib import Path
import g4usim_gui.widgets.run_history_page as module
def install():
    path=Path(__file__).with_name('run_history_page.proposed.py')
    exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),module.__dict__)

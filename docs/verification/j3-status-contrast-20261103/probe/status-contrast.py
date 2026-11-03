import sys,os,json
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'gui'))
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtGui import QPalette
from g4usim_gui.core.theme import SKIN_IDS,skin,apply_appearance,contrast_ratio
app=QApplication([]);app.setStyle('Fusion');out=root/'out/verification/j3-status-contrast-replay';out.mkdir(parents=True,exist_ok=True)
rows=[]
for sid in SKIN_IDS:
 item=skin(sid);apply_appearance(app,item.mode,sid if item.mode=='light' else 'B',sid if item.mode=='dark' else 'C')
 label=QLabel('Completed / 本轮已完成');label.setProperty('uiRole','statusChip');label.setProperty('statusRole','success');label.resize(300,40);label.show();app.processEvents()
 frame=label.grab().toImage();bg=frame.pixelColor(5,20).name();fg=label.palette().color(QPalette.WindowText).name()
 row={'skin':sid,'foreground':fg,'actual_background':bg,'contrast':contrast_ratio(fg,bg),'font_pixel_size':label.font().pixelSize()};row['passed']=row['contrast']>=4.5;rows.append(row)
 frame.save(str(out/(sid+'.png')));label.close();label.deleteLater();app.processEvents()
(out/'report.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps([x for x in rows if not x['passed']],indent=2))
sys.exit(0 if all(x['passed'] for x in rows) else 2)

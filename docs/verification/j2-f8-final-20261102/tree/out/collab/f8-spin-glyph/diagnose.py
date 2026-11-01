"""Read-only product diagnosis in an independent offscreen process; no native input."""
import os,sys,json,tempfile,hashlib
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'gui'));sys.path.insert(0,str(ROOT/'gui/smoke_tests'))
from PySide6.QtCore import QSettings,QRect
from PySide6.QtGui import QFontDatabase,QFontMetrics,QFontInfo
from PySide6.QtWidgets import QApplication,QWizard,QLineEdit,QDoubleSpinBox,QSpinBox,QStyle,QStyleOptionSpinBox,QStyleOptionFrame,QWidget,QFormLayout
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
app=QApplication([]);app.setOrganizationName('F8ReadOnlySpin');app.setApplicationName('OffscreenMetrics')
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,tempfile.mkdtemp(prefix='spin-metrics-'))
for name in ('segoeui.ttf','msyh.ttc'):
 p=Path(os.environ['WINDIR'])/'Fonts'/name
 assert QFontDatabase.addApplicationFont(str(p))>=0
app.setStyle('Fusion');apply_theme(app,'light');set_application_language(app,'zh_CN')
window=MainWindow();window.config_builder_page._backend_timer.stop();window.config_builder_page.schedule_backend_geometry=lambda*a,**k:None
wizard=NewSimulationWizard(window);wizard.spec.events=1000;wizard.spec.seed=12345
rows=[]
def pump():
 for _ in range(4):app.processEvents()
def rect(r):return [r.x(),r.y(),r.width(),r.height()]
def measure(name,w):
 is_spin=isinstance(w,(QDoubleSpinBox,QSpinBox));edit=w.findChild(QLineEdit) if is_spin else w
 font=QFontInfo(edit.font());fm=QFontMetrics(edit.font());opt=QStyleOptionFrame();edit.initStyleOption(opt)
 content=edit.style().subElementRect(QStyle.SE_LineEditContents,opt,edit)
 m=edit.textMargins();text=edit.text()
 row={'name':name,'class':type(w).__name__,'control':rect(w.rect()),'font':{'family':font.family(),'pixel_size':font.pixelSize(),'point_size':font.pointSizeF(),'height':fm.height(),'ascent':fm.ascent(),'descent':fm.descent(),'text_tight_bounds':rect(fm.tightBoundingRect(text))},'text':text,'editor_geometry':rect(edit.geometry()),'editor_minimum':rect(QRect(0,0,edit.minimumWidth(),edit.minimumHeight())),'editor_contents':rect(edit.contentsRect()),'style_line_contents':rect(content),'text_margins':[m.left(),m.top(),m.right(),m.bottom()],'style_frame_width':opt.lineWidth,'editor_stylesheet':edit.styleSheet()}
 if is_spin:
  spinopt=QStyleOptionSpinBox();w.initStyleOption(spinopt)
  row['spin_edit_field']=rect(w.style().subControlRect(QStyle.CC_SpinBox,spinopt,QStyle.SC_SpinBoxEditField,w))
  row['spin_up']=rect(w.style().subControlRect(QStyle.CC_SpinBox,spinopt,QStyle.SC_SpinBoxUp,w))
 row['editor_rect_height_minus_font_height']=edit.height()-fm.height()
 rows.append(row)
 w.grab().save(str(out/(name+'.png')))
try:
 wizard.show();pump();wizard.next();pump();wizard.next();pump()
 measure('wizard_source_energy',wizard.source_page.energy)
 wizard.grab().save(str(out/'wizard-source.png'))
 wizard.next();pump()
 measure('wizard_run_events',wizard.run_page.events);measure('wizard_run_threads',wizard.run_page.threads);measure('wizard_run_seed',wizard.run_page.seed)
 wizard.grab().save(str(out/'wizard-run.png'))
 comparison=QWidget();form=QFormLayout(comparison)
 for name,override in [('production',None),('nested_editor_reset','QAbstractSpinBox QLineEdit { min-height: 0px; border: 0px; padding: 0px; border-radius: 0px; }')]:
  double=QDoubleSpinBox();double.setDecimals(4);double.setRange(0,1e6);double.setSuffix(' MeV');double.setValue(100)
  if override:double.setStyleSheet(override)
  form.addRow(name,double)
  integer=QSpinBox();integer.setRange(0,100000);integer.setValue(1000)
  if override:integer.setStyleSheet(override)
  form.addRow(name+' int',integer)
 comparison.resize(680,220);comparison.show();pump()
 for i in range(form.rowCount()):
  label=form.itemAt(i,QFormLayout.LabelRole).widget();w=form.itemAt(i,QFormLayout.FieldRole).widget();measure('comparison_'+label.text(),w)
 comparison.grab().save(str(out/'comparison.png'))
 (out/'metrics.json').write_text(json.dumps({'scope':'offscreen component measurement; does not manipulate live native process','dpr':window.devicePixelRatioF(),'app_font':app.font().toString(),'rows':rows,'product_sha':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['gui/g4usim_gui/core/theme.py','gui/g4usim_gui/widgets/new_simulation_wizard.py','gui/g4usim_gui/core/accessibility.py']}},ensure_ascii=False,indent=2),encoding='utf-8')
 for r in rows:print(r['name'],r['text'],'font',r['font']['family'],r['font']['height'],'control',r['control'],'editor',r['editor_geometry'],'linecontents',r['style_line_contents'],'spinfield',r.get('spin_edit_field'))
 comparison.close();comparison.deleteLater();wizard.reject()
finally:close_window(app,window)

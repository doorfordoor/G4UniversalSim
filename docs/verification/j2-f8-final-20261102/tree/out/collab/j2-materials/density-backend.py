import os,sys,json,subprocess,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'gui'))
from g4usim_gui.editors.material_editor_model import density_internal_value, _CLHEP_G
exe=Path(os.environ['G4USIM_EXE']).resolve()
work=Path(sys.argv[1]).resolve(); work.mkdir(parents=True,exist_ok=False)
cases={
 'g_upper':('1 G/CM3',True), 'g_power_star':('2.7 * G/CM^3',True),
 'kg_upper_star':('2.7*KG/M3',True), 'kg_power':('2.7 KG/M^3',True),
 'mg_upper':('2.7 MG/CM3',True), 'mg_power_star':('2.7 * MG/CM^3',True),
 'overflow_g':('1e308 g/cm3',False), 'intermediate_g':('1e287 g/cm3',False),
 'overflow_kg':('1e308 kg/m3',False), 'overflow_mg':('1e308 mg/cm3',False),
 'underflow':('1e-999 g/cm3',False)}
receipts=[]
for name,(density,valid) in cases.items():
 folder=work/name; folder.mkdir()
 material=folder/'material.ini';material.write_text('[material.Probe]\nmode=mass_fraction\ndensity='+density+'\ncomponents=O:1\n',encoding='utf-8')
 geometry=folder/'geometry.ini';geometry.write_text('[world]\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\n[target]\nsize=1 cm,1 cm,1 cm\nmaterial=Probe\n',encoding='utf-8')
 config=folder/'main.ini';config.write_text('[materials]\nfile='+material.as_posix()+'\n[geometry]\ntemplate=simple_box\nconfig='+geometry.as_posix()+'\n',encoding='utf-8')
 macro=folder/'run.mac';macro.write_text('/run/initialize\n/run/beamOn 1\n',encoding='utf-8')
 output=folder/'run'
 result=subprocess.run([str(exe),'--config',str(config),'--macro',str(macro),'--output',str(output),'--threads','1'],cwd=folder,capture_output=True,text=True,errors='replace',timeout=90)
 (folder/'backend.log').write_text(result.stdout+result.stderr,encoding='utf-8')
 gui=density_internal_value(density)
 assert (gui is not None)==valid,(density,gui)
 assert result.returncode==(0 if valid else 1),(density,result.returncode)
 if valid:
  summary=(output/'run_summary.txt').read_text(encoding='utf-8')
  assert 'status = completed' in summary and 'completed_events = 1' in summary
  data=json.loads((output/'effective_config_finalization.json').read_text())
  actual=[e['observed'] for e in data['evidence'] if e['path'].endswith('material:Probe/density')][-1]
  expected=gui/(_CLHEP_G/1000.)
  assert abs(actual-expected)<abs(expected)*1e-12,(actual,expected)
 receipts.append({'case':name,'density':density,'exit_code':result.returncode,'valid':valid})
(work/'receipt.json').write_text(json.dumps({'exe':str(exe),'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'cases':receipts},indent=2),encoding='utf-8')
print('Density backend targeted cases passed:',len(receipts))

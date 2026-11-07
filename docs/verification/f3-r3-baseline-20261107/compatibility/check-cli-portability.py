from pathlib import Path
import sys,importlib.util,subprocess,json,hashlib,platform
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True);source=root/'scripts/measure_output_performance.py'
spec=importlib.util.spec_from_file_location('measurement_cli_check',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert hashlib.sha256(source.read_bytes()).hexdigest()=='167ba575bda73fa68e2a01a3b898a38f77bf8465c89cf5110296c7ef35f4c656'
combos=[('hits','csv'),('hits','root'),('mesh','csv'),('mesh','root')]
expected=[combos,[combos[1],combos[2],combos[3],combos[0]],[combos[2],combos[3],combos[0],combos[1]],[combos[3],combos[0],combos[1],combos[2]],combos]
for i,wanted in enumerate(expected):assert m.ordered_combos(combos,'blocked',i)==wanted and m.ordered_combos(combos,'legacy',i)==combos
for w,f in combos:
 assert m.render_config(w,f,1000)==m.render_config(w,f,2000)
 assert b'threads = 2' in m.render_config(w,f,2000) and b'seed = 4242' in m.render_config(w,f,2000)
 assert m.render_macro(w,2000)==m.render_macro(w,1000).replace(b'beamOn 1000',b'beamOn 2000')
p=subprocess.run([sys.executable,'-B',str(source),'--help'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=root)
(out/(sys.platform+'-help.log')).write_bytes(p.stdout);assert p.returncode==0 and b'--order' in p.stdout and b'blocked' in p.stdout
result={'status':'pass','platform':platform.platform(),'python':platform.python_version(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scope':'CLI help, blocked/legacy schedule and input rendering only; no Geant4, GUI, physics benchmark or Linux RSS claim','geant4_started':False}
(out/(sys.platform+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8',newline=chr(10));print(json.dumps(result),flush=True)


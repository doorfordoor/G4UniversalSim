from pathlib import Path
import os,sys,ast,copy,json,hashlib,ctypes,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;OWNER=ROOT/'out/collab/j2-geometry-reload-path-18c5858'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
candidate=OWNER/'smoke_j2_geometry.py';original=ROOT/'gui/smoke_tests/smoke_j2_geometry.py'
assert sha(candidate)=='b3fefeac58f044c99021d1caf7812fd66c8fe41bd14fb94ebcf8facf0c1cb6bd'
assert sha(OWNER/'fix.patch')=='646d69038b11b24ee59145493de3df0d33ee9f4ae36d32d28ed96e21fdb85930'
a=ast.parse(original.read_text(encoding='utf-8'));b=ast.parse(candidate.read_text(encoding='utf-8'));compile(b,str(candidate),'exec')
class Normalize(ast.NodeTransformer):
 def visit_Assign(self,n):
  if len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='reloaded_source':return None
  return self.generic_visit(n)
 def visit_Assert(self,n):
  text=ast.unparse(n.test)
  if text=='page.geometry_document.source_path == str(source.resolve())':return ast.parse('assert page.geometry_document.source_path==str(source)').body[0]
  if text=='reloaded_source.samefile(source)' or text=='hashlib.sha256(reloaded_source.read_bytes()).hexdigest() == hashlib.sha256(source.read_bytes()).hexdigest()':return None
  return self.generic_visit(n)
assert ast.dump(a,include_attributes=False)==ast.dump(Normalize().visit(copy.deepcopy(b)),include_attributes=False)
lexical=[n for n in ast.walk(b) if isinstance(n,ast.Assert) and ast.unparse(n.test)=='page.geometry_document.source_path == str(source)'];assert len(lexical)==1
tracked=['gui/smoke_tests/smoke_j2_geometry.py','gui/g4usim_gui/widgets/config/geometry.py','gui/g4usim_gui/parsers/geometry_parser.py','gui/g4usim_gui/editors/geometry_editor_model.py','tools/test_assert_probe.py']
before={p:sha(ROOT/p) for p in tracked}
r=subprocess.run(['git','-c','core.longpaths=true','apply','--check',str(OWNER/'fix.patch')],cwd=ROOT,capture_output=True,text=True);assert r.returncode==0,r.stderr
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path.insert(0,str(ROOT/'gui'))
from PySide6.QtWidgets import QApplication
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
app=QApplication([]);page=ConfigBuilderPage();page._backend_timer.stop();page.schedule_backend_geometry=lambda *a,**k:None
folder=OUT/'independent geometry folder with spaces';folder.mkdir(exist_ok=True)
source=folder/'long sample geometry source.ini';source.write_text('[world]\nshape=box\nsize=2 m,2 m,2 m\nmaterial=G4_AIR\n\n[volume.Independent]\nparent=world\nshape=box\nsize=1 cm,1 cm,1 cm\nmaterial=G4_WATER\n',encoding='utf-8')
getshort=ctypes.windll.kernel32.GetShortPathNameW;getshort.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint];getshort.restype=ctypes.c_uint
size=getshort(str(source.resolve()),None,0);assert size>0
buffer=ctypes.create_unicode_buffer(size);assert getshort(str(source.resolve()),buffer,size)>0
short=Path(buffer.value);assert short.samefile(source) and str(short)!=str(source.resolve())
rows=[]
try:
 for requested in [source,short]:
  page.geometry_config.setText(str(requested));page.reload_geometry()
  actual=page.geometry_document.source_path
  assert actual==str(requested.resolve()) and Path(actual).samefile(requested) and sha(Path(actual))==sha(requested)
  assert not page.geometry_document.source_errors and page.geometry_summary._f4_read_success
  names=[v.name for v in page.geometry_document.volumes];assert 'Independent' in names
  rows.append({'case':'successful_read','requested':str(requested),'canonical':actual,'old_literal_assert_would_pass':actual==str(requested),'samefile':True,'sha256':sha(requested)})
  # Force an existing lexical alias anchor, as the permanent failed-read fixture does.
  page.geometry_document.source_path=str(short)
  page.seed.setText('  invalid seed preserved  ');page.volume_details.fields['parameters'].setText('  invalid draft  ')
  page.geometry_config.setText(str(folder/'missing geometry.ini'));page.reload_geometry()
  assert page.geometry_document.source_path==str(short)
  assert page.geometry_document.source_path!=str(short.resolve())
  assert [v.name for v in page.geometry_document.volumes]==names and page.geometry_document.source_errors
  assert not page.geometry_summary._f4_read_success
  assert page.seed.text()=='  invalid seed preserved  ' and page.volume_details.fields['parameters'].text()=='  invalid draft  '
  try:generate_geometry_ini_text(page.geometry_document)
  except ValueError:pass
  else:assert False,'failed read allowed generation'
  rows.append({'case':'failed_read_preserves_lexical','retained':page.geometry_document.source_path,'canonical_differs':True,'rows_drafts_preserved':True,'generation_rejected':True})
 # Same bytes at a different real path must not pass new identity conjunction.
 twin=folder/'different real source.ini';twin.write_bytes(source.read_bytes());assert sha(twin)==sha(source) and not twin.samefile(source)
 assert not (str(twin)==str(source.resolve()) and twin.samefile(source) and sha(twin)==sha(source))
 rows.append({'case':'same_bytes_different_file_negative','content_equal':True,'samefile':False,'candidate_identity_would_reject':True})
finally:
 page.close();page.deleteLater();app.processEvents()
assert all(sha(ROOT/p)==v for p,v in before.items())
author=json.loads((OWNER/'receipt.json').read_text(encoding='utf-8'))
for row in author['results']:assert sha(OWNER/row['log'])==row['log_sha256']
receipt={'passed':True,'scope':'minimal actual offscreen reload + real Windows8.3 alias, no full smoke/native/backend/profile','candidate_sha256':sha(candidate),'patch_sha256':sha(OWNER/'fix.patch'),'AST_only_success_branch_change_proven':True,'failed_literal_assert_preserved':True,'patch_check_exit':0,'cases':rows,'tracked_unchanged':True,'source_sha256_before':before,'actual_CI_TEMP_spelling_not_proven':True}
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt,indent=2))


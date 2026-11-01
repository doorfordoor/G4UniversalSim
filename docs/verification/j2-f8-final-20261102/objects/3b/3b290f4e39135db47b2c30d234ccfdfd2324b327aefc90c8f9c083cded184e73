from pathlib import Path
import ast,json,hashlib,re,subprocess
ROOT=Path(__file__).resolve().parents[3];OWNER=ROOT/'out/collab/f8-history-spacer-combined';OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
combined=OWNER/'smoke_f8_accessibility.proposed.py';patch=OWNER/'smoke_f8_accessibility.patch'
assert sha(combined)=='943c92a0cdd0650511b7c8ce45378ebcbddc06b7f55b90835317eb44d3a59e95'
assert sha(patch)=='0f8f8fd2f73fb9cbd7636259cb059c2652fdc041637754d1027db63b7b07f548'
assert b'\r\n' not in patch.read_bytes() and b'\r\n' not in combined.read_bytes()
parse=lambda p:ast.parse(p.read_text(encoding='utf-8'))
functions=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
oldtree=parse(ROOT/'gui/smoke_tests/smoke_f8_accessibility.py');newtree=parse(combined)
old=functions(oldtree);new=functions(newtree);added={'test_history_directory_accessibility','test_layout_item_compatibility'}
assert new.keys()-old.keys()==added
for name in old.keys()-{'main'}:assert ast.dump(old[name],include_attributes=False)==ast.dump(new[name],include_attributes=False),name
history=functions(parse(ROOT/'out/collab/f8-history-label/v2/smoke_f8_accessibility.proposed.py'))
spacer=functions(parse(ROOT/'out/collab/f8-layout-item-compat/smoke_f8_accessibility.proposed.py'))
for name,owner in [('test_history_directory_accessibility',history),('test_layout_item_compatibility',spacer)]:
 assert ast.dump(new[name],include_attributes=False)==ast.dump(owner[name],include_attributes=False),name
calls=[ast.unparse(n) for n in new['main'].body[-3:-1]]
assert calls==['test_history_directory_accessibility(app, args.output)','test_layout_item_compatibility(app)'],calls
del new['main'].body[-3:-1];assert ast.dump(new['main'],include_attributes=False)==ast.dump(old['main'],include_attributes=False)
# Top-level imports and every other original node also remain identical.
newtree.body=[n for n in newtree.body if not (isinstance(n,ast.FunctionDef) and n.name in added)]
assert ast.dump(newtree,include_attributes=False)==ast.dump(oldtree,include_attributes=False)
receipt=json.loads((OWNER/'receipt.json').read_text(encoding='utf-8'))
before=json.loads((OWNER/'identity-before.json').read_text(encoding='utf-8'));after=json.loads((OWNER/'identity-after.json').read_text(encoding='utf-8'));assert before==after
for name,item in receipt['identities'].items():assert sha(ROOT/name)==item['sha256'],name
for row in receipt['runs']:
 log=OWNER/row['log'];text=log.read_text(encoding='utf-8')
 assert sha(log)==row['log_sha256_raw_bytes']
 assert re.findall(r'^G4USIM_ASSERTS=(\d+)',text,re.M)==['595']
 assert 'RuntimeWarning' in text
 assert row['exit_code']==0 and row['process_ended'] and row['assertions_v3']==595
# Historical independent proposals retain raw original artifacts and each reported log.
for directory in ['f8-history-label/v2','f8-layout-item-compat']:
 folder=ROOT/'out/collab'/directory;r=json.loads((folder/'receipt.json').read_text(encoding='utf-8'))
 for name,item in r['files'].items():assert sha(folder/name)==item['sha256']
 for row in r['runs']:
  name=row.get('log','scale'+str(row.get('scale'))+'.log');expected=row.get('sha256',row.get('log_sha256'))
  assert sha(folder/name)==expected,name
patches=[ROOT/'out/collab/f8-history-label/v2/run_history_page.patch',ROOT/'out/collab/f8-layout-item-compat/accessibility.patch',patch]
run=subprocess.run(['git','apply','--check',*[str(p) for p in patches]],cwd=ROOT,capture_output=True,text=True);assert run.returncode==0,run.stderr
result={'passed':True,'scope':'minimal AST/raw hashes/apply-check only; no Qt/profile/backend/native/build execution','combined_sha256':sha(combined),'patch_sha256':sha(patch),'old_full_module_AST_after_removing_two_functions_and_calls_identical':True,'history_added_AST_matches_reviewed_v2':True,'spacer_added_AST_matches_reviewed_final':True,'main_added_calls':calls,'both_author595_log_SHA_and_markers_match':True,'before_after_identity_equal':True,'recorded_identities_match_current_bytes':True,'original519_492_receipts_artifact_and_log_SHA_preserved':True,'three_patch_apply_check_exit':run.returncode,'applied':False}
(OUT/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

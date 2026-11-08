"""Frozen production phase-state component wrapper; --help launches nothing."""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def require(condition,message):
    if not condition: raise AssertionError(message)
    assert condition,message
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,data):Path(p).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path)
    parser.add_argument('--expected-source-fingerprint')
    parser.add_argument('--timeout',type=int,default=180)
    args=parser.parse_args()
    require(args.timeout>0,'positive timeout')
    probe=(args.probe or Path(os.environ.get('G4USIM_PHASE_STATE_CHECK') or str(Path(os.environ['G4USIM_EXE']).with_name('phaseSpaceStateCheck.exe' if os.name=='nt' else 'phaseSpaceStateCheck')))).resolve()
    require(probe.is_file(),'probe missing')
    if not args.expected_source_fingerprint:
        from run_m0_tests import workspace_source_fingerprint
        args.expected_source_fingerprint=workspace_source_fingerprint()
    evidence=Path(os.environ['G4USIM_TEST_EVIDENCE_DIR']).resolve();evidence.mkdir(parents=True,exist_ok=True)
    trial=Path(tempfile.mkdtemp(prefix='phase-state-',dir=evidence))
    receipt={'status':'running','binary':str(probe),'binary_sha256':sha(probe),'probe_sha256':sha(ROOT/'tools/phaseSpaceStateCheck.cc'),'wrapper_sha256':sha(__file__),'expected_source_fingerprint':args.expected_source_fingerprint,'processes':[]}
    save(trial/'receipt.json',receipt)
    try:
        env=os.environ.copy();env.pop('G4USIM_TEST_OUTPUT_FAULT',None)
        for name,argv in [('identity',[str(probe),'--identity']),('component',[str(probe),str(trial/'native')])]:
            require(sha(probe)==receipt['binary_sha256'],'binary drift before process')
            process={'argv':argv,'cwd':str(trial),'exit_code':None};receipt['processes'].append(process)
            with (trial/(name+'.stdout.log')).open('wb') as stdout,(trial/(name+'.stderr.log')).open('wb') as stderr:
                result=subprocess.run(argv,cwd=trial,env=env,stdout=stdout,stderr=stderr,timeout=args.timeout)
            process['exit_code']=result.returncode;save(trial/'receipt.json',receipt)
            require(result.returncode==0 and sha(probe)==receipt['binary_sha256'],name+' process failed/drift')
            if name=='identity':
                identity=json.loads((trial/'identity.stdout.log').read_text(encoding='utf-8-sig'))
                require(identity['source_fingerprint']==args.expected_source_fingerprint,'source mismatch')
                require(identity['probe_sha256']==receipt['probe_sha256'],'probe mismatch')
                require(identity['core_only'] is False,'isolated core-only build is not formal component coverage')
                receipt['identity']=identity
        raw=json.loads((trial/'native/result.json').read_text());require(raw['status']=='pass' and raw['identity']==receipt['identity'],'raw identity/status')
        require(type(raw['checks']) is int and raw['checks']>0,'canonical checks missing')
        markers=re.findall(r'^Phase space state checks passed: (\d+)\s*$',(trial/'component.stdout.log').read_text(),re.M)
        require(markers==[str(raw['checks'])],'canonical marker mismatch')
        first=json.loads((trial/'native/first-step.json').read_text());require(first['transport_steps']==1,'first step not observed')
        require(first['charge_eplus']==5.96566726277173 and first['mass_MeV']>0 and 0<first['beta']<1,'first-step dynamic readback')
        import csv
        with (trial/'native/roundtrip.csv').open(newline='') as stream:
            reader=csv.DictReader(stream);rows=list(reader)
            require(len(reader.fieldnames)==22 and reader.fieldnames[-1]=='polarization_z' and len(rows)==1,'v3 roundtrip layout')
            require(rows[0]['electron_occupancy']=='['+';'.join(['4']+['0']*19)+']','actual roundtrip occupancy')
            require(float(rows[0]['dynamic_mass_MeV'])==first['mass_MeV'],'roundtrip/first-step mass')
        # Inject a boundary into the real production callback, then use real application finalization.
        # This is explicitly not a transported event or a successful simulation.
        for mode in ('capture-decay-time','capture-decay-products'):
            work=trial/mode;work.mkdir()
            geometry=work/'geometry.ini';geometry.write_text('[world]\nshape=box\nsize=2 m,2 m,2 m\nmaterial=G4_Galactic\n')
            config=work/'main.ini';config.write_text(f'[run]\nthreads=1\nseed=20261109\n[output]\nformat=csv\n[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n[physics]\nreference=FTFP_BERT\n[source]\nparticle=proton\nenergy=120 MeV\nposition_type=point\nposition=0,0,0 mm\ndirection=+x\n[scoring]\nenabled=true\nhits=false\nevent_edep=false\nedep=false\n[phase_space]\nvolume=world\nparticles=all\nkill=false\n')
            argv=[str(probe),'--'+mode,str(config),str(work/'native')]
            record={'argv':argv,'cwd':str(work),'expected_exit':1,'input_sha256':{'main.ini':sha(config),'geometry.ini':sha(geometry)}}
            receipt['processes'].append(record);save(trial/'receipt.json',receipt)
            with (work/'stdout.log').open('wb') as stdout,(work/'stderr.log').open('wb') as stderr:
                process=subprocess.run(argv,cwd=work,env=env,stdout=stdout,stderr=stderr,timeout=args.timeout)
            record['exit_code']=process.returncode
            require(process.returncode==1 and sha(probe)==receipt['binary_sha256'],'capture failure exit/identity')
            failure=json.loads((work/'native/result.json').read_text())
            require(failure['status']=='expected_failure' and failure['identity']==receipt['identity'],'capture raw result identity')
            require(failure['callback_invoked'] is True and failure['synthetic_boundary'] is True and failure['beam_on_called'] is False,'callback evidence scope')
            metadata=json.loads((work/'native/output/run_metadata.json').read_text());summary=metadata['values']
            require(summary['status']=='failed' and int(summary['program_exit_code'])!=0,'production nonzero failed summary')
            require(summary['output_failure_stage']=='phase_space_capture' and 'preassigned decay' in summary['output_failure_message'],'capture first cause in summary')
            require(summary['source_fingerprint']==args.expected_source_fingerprint,'capture summary source')
            require(int(summary['actual_completed_event_count'])==0 and int(summary['run_count'])==0,'injected callback is not a run')
            require(not list((work/'native/output').glob('phase_space*.csv')),'unsupported state written as phase output')
            require(sha(config)==record['input_sha256']['main.ini'] and sha(geometry)==record['input_sha256']['geometry.ini'],'capture input drift')
            record['raw']=failure
        require(sha(ROOT/'tools/phaseSpaceStateCheck.cc')==receipt['probe_sha256'] and sha(__file__)==receipt['wrapper_sha256'],'source/wrapper drift')
        receipt.update(status='passed',raw=raw,first_step=first)
    except Exception as error:receipt.update(status='failed',error=repr(error))
    receipt['artifacts']={p.relative_to(trial).as_posix():sha(p) for p in trial.rglob('*') if p.is_file() and p!=trial/'receipt.json'}
    save(trial/'receipt.json',receipt);print(f"phase state {receipt['status']}: {trial/'receipt.json'}")
    return 0 if receipt['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())

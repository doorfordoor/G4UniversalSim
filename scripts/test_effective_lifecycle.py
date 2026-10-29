#!/usr/bin/env python3
"""Full-2C lifecycle black-box gate. Requires an explicitly selected NEW build."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile


def fields(snapshot):
    return {item['path']: item for item in snapshot['fields']}


def validate(snapshot):
    assert snapshot['schema'] == 'g4usim_effective_config_v1'
    assert type(snapshot['revision']) is int and snapshot['revision'] >= 0
    for field in snapshot['fields']:
        if field.get('application_status') != 'applied':
            continue
        assert snapshot['stage'] != 'configure', field
        assert field['applied_revision'] == field['revision'], field
        assert field['evidence_level'] in ('kernel_constructed','thread_applied','run_validated'), field
        receipts = [receipt for receipt in snapshot['evidence']
                    if receipt.get('path') == field['path']
                    and receipt.get('application_status') == 'applied'
                    and receipt.get('matches_resolved_value') is True]
        assert receipts, field
        assert any(receipt.get('configuration_generation') == field.get('configuration_generation')
                   for receipt in receipts), field
    for receipt in snapshot.get('evidence', []):
        assert receipt['thread_id'] == snapshot['thread_id'], receipt
        if snapshot['run_id'] is not None and receipt.get('run_id') is not None:
            assert receipt['run_id'] == snapshot['run_id'], receipt


def component():
    root=Path(__file__).resolve().parents[1]
    import shlex
    configured=os.environ.get('CXX')
    compiler=shlex.split(configured,posix=os.name!='nt') if configured else []
    if os.name=='nt':
        # Windows shlex preserves quotes; subprocess expects bare argv tokens.
        compiler=[token[1:-1] if len(token)>1 and token[0]==token[-1] and token[0] in ('\"', "'") else token
                  for token in compiler]
    if not compiler:
        found=next((shutil.which(name) for name in ('g++','clang++','cl') if shutil.which(name)),None)
        assert found, 'C++17 compiler required (set CXX or configure PATH)'
        compiler=[found]
    production=(root/'src/Core/EffectiveSimulation.cc').read_text(encoding='utf-8')
    query=production[production.index('bool IsReadOnlyCommand('):production.index('void AddOrigin(')]
    harness=r'''
#include "Config/EffectiveReceiptView.hh"
#include <iostream>
#include <stdexcept>
using namespace effective_config;
QUERY
int main() {
 Registry registry;Field value;value.path="/field/objects/Local/magnetic";
 value.resolved=Value::Array{0,0,1};value.configuration_generation=2;
 value.evidence_level=EvidenceLevel::ManagerAccepted;
 Field scope=value;scope.path="/field/objects/Local/scope";scope.resolved="local";
 registry.Commit({value,scope});const auto snapshot=registry.Capture("run_begin",1);const auto frozen=snapshot.ToJson();
 Value::Object results;
 const auto receipt=[&](std::string path,std::string target,std::string status,int run=1,int generation=2,std::string stage="run_begin",std::string level="thread_applied") {
  const auto& field=snapshot.Fields().at(path);
  return Value(Value::Object{{"path",path},{"logical_volume",target},{"stage",stage},{"run_id",run<0?Value():Value(run)},
   {"thread_id",0},{"configuration_generation",generation},{"observed",field.resolved},
   {"resolved_sha256",input_provenance::Sha256(field.resolved.ToJson())},{"application_status",status},
   {"evidence_level",level},{"evidence_source","independent object"}});
 };
 const auto evaluate=[&](const char* name,Value::Array evidence) {
  const auto view=ReduceRuntimeReceipts(snapshot,evidence,0,1);
  auto annotated=snapshot.WithApplicationEvidence(view.annotations);
  results[name]=std::string(annotated.Fields().at(value.path).application_status==ApplicationStatus::Applied?"applied":
   annotated.Fields().at(value.path).application_status==ApplicationStatus::Failed?"failed":
   annotated.Fields().at(value.path).application_status==ApplicationStatus::Unknown?"unknown":"not_applied");
 };
 evaluate("success",{receipt(value.path,"A","applied")});
 evaluate("other_target_failed",{receipt(value.path,"A","failed"),receipt(value.path,"B","applied")});
 evaluate("other_target_unknown",{receipt(value.path,"A","unknown"),receipt(value.path,"B","applied")});
 evaluate("binding_failed",{receipt(scope.path,"B","failed"),receipt(value.path,"A","applied")});
 evaluate("same_target_failure_sticky",{receipt(value.path,"A","failed"),receipt(value.path,"A","applied")});
 evaluate("old_generation",{receipt(value.path,"A","applied",1,1)});
 evaluate("old_unknown_not_veto",{receipt(value.path,"A","applied"),receipt(value.path,"A","unknown",1,1)});
 evaluate("other_run",{receipt(value.path,"A","applied",0)});
 evaluate("runless_runtime",{receipt(value.path,"A","applied",-1)});
 evaluate("runless_construction",{receipt(value.path,"A","applied",-1,2,"field_construct")});
 evaluate("invalid_level",{receipt(value.path,"A","applied",1,2,"run_begin","none")});
 if(snapshot.ToJson()!=frozen || registry.Capture("run_begin",1).ToJson()!=frozen)throw std::runtime_error("snapshot mutated");
 results["clear_reference_is_mutation"]=!IsReadOnlyCommand("/aihl/physics/clearreferencelist");
 results["list_is_readonly"]=IsReadOnlyCommand("/aihl/physics/listavailablereferences");
 results["substring_is_mutation"]=!IsReadOnlyCommand("/aihl/physics/setexportlist");
 std::cout<<Value(results).ToJson()<<"\n";
}
'''.replace('QUERY',query)
    with tempfile.TemporaryDirectory(prefix='g4usim-runtime-view-') as temp:
        work=Path(temp);source=work/'view.cc';source.write_text(harness,encoding='utf-8')
        executable=work/('view.exe' if os.name=='nt' else 'view')
        inputs=[str(source),str(root/'src/Config/EffectiveConfig.cc'),str(root/'src/Config/InputProvenance.cc')]
        if Path(compiler[0]).stem.lower() in ('cl','clang-cl'):
            command=compiler+['/nologo','/std:c++17','/utf-8','/EHsc','/I'+str(root/'include')]
            command+=inputs+['/Fe:'+str(executable)]
        else:
            command=compiler+['-std=c++17','-Wall','-Wextra','-pedantic','-I',str(root/'include')]
            command+=inputs+['-o',str(executable)]
        built=subprocess.run(command,cwd=work,capture_output=True,text=True,timeout=120)
        assert built.returncode==0,built.stdout+built.stderr
        ran=subprocess.run([str(executable)],cwd=work,capture_output=True,text=True,timeout=30)
        assert ran.returncode==0,ran.stdout+ran.stderr
        result=json.loads(ran.stdout)
        for name in ('success','old_unknown_not_veto','runless_construction'):
            assert result[name]=='applied',(name,result)
        for name in ('other_target_failed','binding_failed','same_target_failure_sticky'):
            assert result[name]=='failed',(name,result)
        for name in ('old_generation','other_run','runless_runtime'):
            assert result[name]=='not_applied',(name,result)
        assert result['other_target_unknown']=='unknown' and result['invalid_level']=='unknown',result
        assert result['clear_reference_is_mutation'] and result['list_is_readonly'] and result['substring_is_mutation']
    print('PASS: independent receipt reducer, target failure isolation, generation/run scopes, immutable snapshots, exact read-only classification')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--component',action='store_true')
    parser.add_argument('--executable',default=os.environ.get('G4USIM_EXE'))
    args=parser.parse_args()
    if args.component:
        component()
        return 0
    assert args.executable, 'Set G4USIM_EXE or --executable to the newly built candidate'
    executable=Path(args.executable).resolve()
    assert executable.is_file(), executable
    with tempfile.TemporaryDirectory(prefix='g4usim-2c-lifecycle-') as temp:
        root=Path(temp)
        def run(name,commands,*,dry=False,inspect=False,extra="",fail=False,block_snapshot=False):
            work=root/name
            work.mkdir()
            output=work/'output'
            geometry=work/'geometry.ini'
            geometry.write_text('[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n'
                '[volume.Det]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\nmaterial=G4_Si\nsensitive=true\n',encoding='utf-8')
            config=work/'main.ini'
            config.write_text('[geometry]\ntemplate=hierarchical\nconfig='+geometry.as_posix()+'\n'
                              '[run]\nthreads=2\n[output]\ndir='+output.as_posix()+
                              '\n[source]\nparticle=gamma\nenergy=2 MeV\n'
                              '[scoring]\nenabled=true\nevent_edep=true\n'+extra,encoding='utf-8')
            macro=work/'commands.mac'
            macro.write_text(commands,encoding='utf-8')
            command=[str(executable),'--config',str(config),'--macro',str(macro)]
            if dry:
                command.append('--dry-run')
            if inspect:
                command.extend(['--dump-effective-config','-'])
            if block_snapshot:
                (output/'effective_config_configure.json').mkdir(parents=True)
            process=subprocess.run(command,cwd=work,capture_output=True,text=True,
                                   encoding='utf-8',errors='replace',timeout=120)
            if fail:
                assert process.returncode!=0,process.stdout+process.stderr
                summary=(output/'run_summary.txt').read_text(encoding='utf-8')
                assert 'status = failed' in summary,summary
                assert not list(output.glob('*.tmp-*')),list(output.iterdir())
                return summary,output
            assert process.returncode==0, process.stdout+process.stderr
            if inspect:
                snapshot=json.loads(process.stdout)
                validate(snapshot)
                assert snapshot['stage']=='configure' and not snapshot['execution_performed']
                assert not output.exists(), 'inspection created execution output'
                return snapshot
            snapshots={path.name:json.loads(path.read_text(encoding='utf-8'))
                       for path in output.glob('effective_config_*.json')}
            assert 'effective_config_configure.json' in snapshots, sorted(snapshots)
            assert 'effective_config_finalization.json' in snapshots, sorted(snapshots)
            for snapshot in snapshots.values():
                validate(snapshot)
            initial=snapshots['effective_config_configure.json']
            assert initial['stage']=='configure' and initial['run_id'] is None
            assert fields(initial)['/source/energy']['resolved']==2
            assert all(field.get('application_status')!='applied' for field in initial['fields'])
            return snapshots
        run('inspect','/run/initialize\n/run/beamOn 2\n',inspect=True)
        cleared=run('clear-reference','/AIHL/physics/clearReferenceList\n',extra='[physics]\nreference=FTFP_BERT\n')
        assert fields(cleared['effective_config_configure.json'])['/physics/mode']['resolved']=='reference'
        assert fields(cleared['effective_config_finalization.json'])['/physics/mode']['resolved']=='manual'
        rejected,output=run('module-rejection','# location line 1\n/AIHL/scoring/hits true\n',
                            extra='[scoring]\nenabled=false\nevent_edep=false\n[modules]\nscoring=off\n',fail=True)
        assert 'macro_failure_line = 2' in rejected and 'macro_failure_command = /AIHL/scoring/hits true' in rejected,rejected
        assert 'macro_failure_code_available = false' in rejected,rejected
        broken,output=run('snapshot-failure','/run/initialize\n/run/beamOn 2\n',fail=True,block_snapshot=True)
        assert 'effective_config_publish' in broken,broken
        assert (output/'effective_config_configure.json').is_dir()
        assert not any(path.name.startswith('effective_config_configure.json.tmp-') for path in output.iterdir())
        for name,dry in (('no-run',False),('dry-run',True)):
            snapshots=run(name,'/control/echo lifecycle-no-run\n',dry=dry)
            assert snapshots['effective_config_finalization.json']['execution_performed'] is False
            assert not any(snapshot['stage']=='run_begin' for snapshot in snapshots.values())
        changed=run('same-value-new-origin','/AIHL/source/energy 3 MeV\n/run/initialize\n/run/beamOn 2\n/AIHL/source/energy 3 MeV\n')
        final=changed['effective_config_finalization.json']
        energy=fields(final)['/source/energy']
        assert energy['resolved']==3
        assert energy['application_status']!='applied', 'same-value new source must not reuse old application receipt'
        assert any(origin.get('kind')=='macro' for origin in energy['origins'])
        multiple=run('multiple-runs','/run/initialize\n/run/beamOn 2\n/AIHL/source/energy 3 MeV\n/run/beamOn 2\n')
        begins=[snapshot for snapshot in multiple.values() if snapshot['stage']=='run_begin']
        assert {snapshot['run_id'] for snapshot in begins}=={0,1}
        for snapshot in begins:
            assert fields(snapshot)['/source/energy']['resolved']==(2 if snapshot['run_id']==0 else 3)
            if snapshot['role'] in ('worker','sequential'):
                scorer=fields(snapshot)['/scoring/enabled']
                assert scorer['application_status']=='applied', 'execution-thread BeginRun receipt missing'
    print('PASS: frozen configure, nonexecution paths, same-value provenance, scoped multi-run/thread evidence')
    return 0
if __name__=='__main__':
    raise SystemExit(main())

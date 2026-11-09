"""Observe real members of an owned Windows configure Job without changing its verdict."""
import argparse
import ast
import ctypes as c
import hashlib
import json
import os
import sys
from ctypes import wintypes as w
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--self-test', action='store_true')
parser.add_argument('--geant4-prefix', type=Path)
parser.add_argument('--cmake', type=Path)
parser.add_argument('--compiler', type=Path)
parser.add_argument('--repeat', type=int, default=4)
args = parser.parse_args()
assert os.name == 'nt' and 1 <= args.repeat <= 6
repo = args.repo.resolve(strict=True)
out = args.out.resolve()
assert not out.is_relative_to(repo)
out.mkdir()
sys.path.insert(0, str(repo / 'gui'))
import _winapi
from g4usim_gui.core import _install_msvc_auxiliary as auxiliary
from g4usim_gui.core import _install_sdk_process as process

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def dump(path, value):
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,ensure_ascii=True);f.write('\n')

real_api = process._windows_api
real_wait = process._wait_windows_root_with_job_sample

def configure(argv, evidence, env, policy, cmake_build=False):
    evidence.mkdir()
    cwd=evidence/'build' if cmake_build else evidence
    if cmake_build: cwd.mkdir()
    rec = {}
    hooks = {}
    observations = {}

    def api():
        k = real_api()
        create = k.CreateJobObjectW
        def remember(*argv):
            h = create(*argv)
            hooks.update(k=k,job=h)
            return h
        k.CreateJobObjectW = remember
        return k

    def wait(root, deadline, accounting):
        hooks['root'] = root
        return real_wait(root, deadline, accounting)

    def inspect():
        try:
            k, job = hooks['k'], hooks['job']
            for name, spec, return_type in (
                ('OpenProcess',[w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
                ('IsProcessInJob',[w.HANDLE,w.HANDLE,c.POINTER(w.BOOL)],w.BOOL),
                ('QueryFullProcessImageNameW',[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)],w.BOOL),
            ):
                fn=getattr(k,name);fn.argtypes=spec;fn.restype=return_type
            pid_root=rec['root_child']['pid']
            root=hooks.get('root')
            own_root=root is None
            if own_root:
                root=process._win_check(k.OpenProcess(0x1000|0x100000,False,pid_root))
            try:
                root_ct,root_exit,*_=auxiliary._times(k,root)
                assert str(root_ct)==rec['root_child']['creation']
                observations['root_exit_filetime']=str(root_exit)
                observations['root_pid']=pid_root
            finally:
                if own_root: _winapi.CloseHandle(root)
            ids=auxiliary._pid_array(k,job)
            observations['held_job_pids']=sorted(ids)
            observations['members']=[]
            for pid in sorted(ids):
                if pid==pid_root:
                    continue
                row={'pid':pid}
                observations['members'].append(row)
                h=process._win_check(k.OpenProcess(0x1000|0x100000,False,pid))
                try:
                    in_job=w.BOOL()
                    process._win_check(k.IsProcessInJob(h,job,c.byref(in_job)))
                    assert in_job.value
                    start=auxiliary._times(k,h)[0]
                    name=c.create_unicode_buffer(32768)
                    n=w.DWORD(len(name))
                    process._win_check(k.QueryFullProcessImageNameW(h,0,name,c.byref(n)))
                    path=Path(name[:n.value])
                    alive=_winapi.WaitForSingleObject(h,0)==_winapi.WAIT_TIMEOUT
                    row.update(image=str(path),creation_filetime=str(start),still_active=alive,
                               created_before_root_exit=0<start<root_exit,member_of_held_job=True)
                    if policy is not None and path==policy.image:
                        row['selected_auxiliary_file_sha_matches']=sha(path)==policy.sha256
                finally:
                    _winapi.CloseHandle(h)
        except Exception as exc:
            observations['observation_error']={'type':type(exc).__name__,'message':str(exc)}

    process._windows_api=api
    process._wait_windows_root_with_job_sample=wait
    error=None
    try:
        with (evidence/'configure.log').open('xb') as log:
            process.run_owned(argv,cwd=cwd,env=env,output=log,timeout=100,record=rec,
                              owned=lambda:None,running=lambda:None,settling=inspect,msvc_auxiliary=policy)
    except Exception as exc:
        error={'type':type(exc).__name__,'code':getattr(exc,'code',None),'message':str(exc)}
    finally:
        process._windows_api=real_api
        process._wait_windows_root_with_job_sample=real_wait
    data={'argv':list(map(str,argv)),'command':rec,'passive_job_members':observations,'error':error}
    dump(evidence/'trace.json',data)
    return data

if args.self_test:
    exe=Path(sys.executable).resolve(strict=True)
    source="import subprocess,sys,time; subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(30)']); time.sleep(.2)"
    row=configure([exe,'-I','-B','-c',source],out/'self-test',os.environ.copy(),None)
    members=row['passive_job_members']['members']
    assert 'observation_error' not in row['passive_job_members']
    expected=[x for x in members if Path(x['image']).resolve(strict=True)==exe]
    assert len(expected)==1 and all(x['member_of_held_job'] and x['still_active'] and x['created_before_root_exit']
                                   for x in members)
    assert row['command']['active_after_root_signal']==len(members)
    assert row['error']['code']=='sdk_descendants_remaining' and row['command']['container_empty'] and row['command']['handles_closed']
    print('Observed a real owned residual and preserved its original failure and cleanup.')
else:
    assert args.geant4_prefix and args.cmake and args.compiler
    geant=args.geant4_prefix.resolve(strict=True)
    cmake=args.cmake.resolve(strict=True)
    compiler=args.compiler.resolve(strict=True)
    assert (geant/'lib/cmake/Geant4/Geant4Config.cmake').is_file()
    source=repo/'packaging/build_sdk_package.py'
    names={}
    for n in ast.parse(source.read_text(encoding='utf-8')).body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            k=n.targets[0].id
            if k in ('PROBE_CMAKE','PROBE_SOURCE'):
                names[k]=ast.literal_eval(n.value)
    p=out/'installed-probe-source';p.mkdir()
    (p/'CMakeLists.txt').write_text(names['PROBE_CMAKE'],encoding='utf-8')
    (p/'main.cc').write_text(names['PROBE_SOURCE'],encoding='utf-8')
    env=os.environ.copy()
    env['PATH']=str(geant/'bin')+os.pathsep+env['PATH']
    policy=auxiliary.prepare(compiler)
    if policy is None: raise RuntimeError('Explicit MSVC auxiliary policy could not be pinned')
    dump(out/'inputs.json',{'compiler':str(compiler),'compiler_sha256':sha(compiler),
                           'cmake':str(cmake),'cmake_sha256':sha(cmake),'geant4_config_sha256':sha(geant/'lib/cmake/Geant4/Geant4Config.cmake'),
                           'probe_source_sha256':sha(p/'main.cc'),'probe_cmake_sha256':sha(p/'CMakeLists.txt'),
                           'process_module_sha256':sha(repo/'gui/g4usim_gui/core/_install_sdk_process.py'),
                           'actual_auxiliary':str(policy.image),'actual_auxiliary_sha256':policy.sha256})
    outcomes=[]
    for i in range(args.repeat):
        q=out/f'attempt-{i+1:02d}'
        command=[cmake,'-S',p,'-B',q/'build',f'-DGeant4_DIR={geant / "lib/cmake/Geant4"}','-DCMAKE_BUILD_TYPE=Release',
                 '-G','Ninja',f'-DCMAKE_CXX_COMPILER={compiler}',f'-DCMAKE_PREFIX_PATH={geant}','-DCMAKE_TRY_COMPILE_CONFIGURATION=Release']
        row=configure(command,q,env,policy,cmake_build=True)
        outcomes.append({'number':i+1,'error':row['error'],'job_members':row['passive_job_members'],
                         'auxiliary':row['command'].get('msvc_auxiliary_cleanup')})
        if row['error'] and row['error']['code']=='sdk_descendants_remaining' and row['passive_job_members'].get('members'):
            break
    dump(out/'diagnostic-terminal.json',{'scope':'Hosted configure diagnostic only; no application, installation, uninstall or AR6 signoff',
                                         'attempts':outcomes})
    print(json.dumps(outcomes,ensure_ascii=True))

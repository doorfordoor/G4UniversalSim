"""Finite synthetic B3 admission/quantity regression; no backend or science runs.

Run with --evidence-root NEW_DIRECTORY to preserve every fixture and CLI receipt.
The shared fixture builder is also used by test_detector_analysis.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COUNT = 0
ACTIVE_CASE = None


def check(condition, message='check failed'):
    global COUNT
    if not condition:
        raise AssertionError(message)
    assert condition, message
    COUNT += 1
    if ACTIVE_CASE is not None:
        ACTIVE_CASE['assertions_executed'] += 1


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, text):
    path.write_text(text, encoding='utf-8', newline='\n')


def save_doc(output, doc):
    write(output / 'run_metadata.json', json.dumps(doc, indent=2, allow_nan=False))


def rehash(output, *, inputs=False):
    doc = json.loads((output / 'run_metadata.json').read_bytes())
    for record in doc['generated_files']:
        if record['path'] == 'run_metadata.json':
            continue
        path = output / record['path']
        record.update(sha256=sha(path), size_bytes=path.stat().st_size)
    if inputs:
        for record in doc['provenance']['inputs']:
            path = output.parent / Path(record['path']).name
            record.update(sha256=sha(path), size_bytes=path.stat().st_size)
    save_doc(output, doc)


def fact(output, key, value):
    doc = json.loads((output / 'run_metadata.json').read_bytes())
    text = (output / 'run_summary.txt').read_text()
    old = doc['values'].get(key)
    if old is None:
        raise ValueError(key)
    text = text.replace(f'{key} = {old}\n', f'{key} = {value}\n')
    doc['values'][key] = str(value)
    write(output / 'run_summary.txt', text); save_doc(output, doc); rehash(output)


def fixture(folder, *, kind='device', energy=.662, values=(.1, .2), events=2, zero=False, workers=1):
    """Standalone synthetic format fixture, never a generated or signed native run."""
    folder.mkdir(parents=True); output = folder / 'output'; output.mkdir()
    if kind == 'device':
        source = '[source]\nparticle = proton\nenergy = 50 MeV\nposition_type = plane\nshape = square\nhalfx = 2.5 mm\ncenter = 0 mm, 0 mm, -1 mm\ndirection = 0, 0, 1\n'
        geometry = '[world]\nshape = box\nsize = 200 mm, 200 mm, 200 mm\nmaterial = G4_Galactic\n'
        layers = []
        for name, material, width, center in [('GateOxide', 'G4_SILICON_DIOXIDE', .0001, 1.00005), ('Active', 'G4_Si', .01, 1.0051)]:
            geometry += f'\n[volume.{name}]\nparent = world\nshape = box\nsize = 5 mm, 5 mm, {width} mm\nmaterial = {material}\nposition = 0 mm, 0 mm, {center} mm\nsensitive = true\n'
            layers.append(dict(name=name, material=material, thickness_mm=width, depth_mm=center-width/2))
        geometry += '\n[volume.Substrate]\nparent = world\nshape = box\nsize = 5 mm, 5 mm, 0.3 mm\nmaterial = G4_Si\nposition = 0 mm, 0 mm, 1.1601 mm\n\n[volume.Slice]\nparent = Substrate\nshape = box\nsize = 5 mm, 5 mm, 0.3 mm\nmaterial = G4_Si\nplacement = replica\nreplica_axis = z\nreplica_count = 1\nreplica_width = 0.3 mm\nsensitive = true\n'
        meta = dict(particle='proton', energy_MeV=50, events=events, source_area_cm2=.25,
                    sampled_integral_flux_cm2_s={'proton':None}, layers=layers,
                    slices=[dict(copy=0, depth_mm=1.0101, thickness_mm=.3)], niel_tables={'proton':'si_proton.csv'})
        scoring = '[scoring]\ndose = true\ndisplacement = true\n\n[scoring.displacement]\nproton = si_proton.csv\n'
        write(folder / 'si_proton.csv', 'energy_MeV,niel_MeV_cm2_g\n1,0.01\n100,0.02\n')
    elif kind == 'gamma':
        # Source max_theta is the actual generator's six-significant-digit encoding.
        theta = 10.; cone = (1-math.cos(math.radians(theta)))/2
        source = f'[source]\nparticle = gamma\nenergy = {energy} MeV\nposition_type = point\nposition = 0 mm, 0 mm, 0 mm\nangular = isotropic\ndirection = 0, 0, 1\nmax_theta = 10 deg\n'
        geometry = '[world]\nmaterial = G4_Galactic\n\n[volume.Crystal]\nparent = world\nshape = tubs\nparameters = 0 mm, 10 mm, 10 mm, 0 deg, 360 deg\nmaterial = G4_SODIUM_IODIDE\nposition = 0 mm, 0 mm, 110 mm\nsensitive = true\n'
        meta = dict(kind=kind, particle='gamma', energy_MeV=energy, events=events, crystal='NaI', material='G4_SODIUM_IODIDE',
                    radius_mm=10, length_mm=20, housing_mm=0, distance_mm=100, cone_half_angle_deg=theta, cone_fraction_of_4pi=cone)
        scoring = '[scoring]\nevent_edep = true\n'
    else:
        source = f'[source]\nparticle = proton\nenergy = {energy} MeV\nposition_type = plane\nshape = square\nhalfx = 2.5 mm\ncenter = 0 mm, 0 mm, -1 mm\ndirection = 0, 0, 1\n'
        geometry = '[world]\nmaterial = G4_Galactic\n\n[volume.Pad]\nparent = world\nshape = box\nsize = 10 mm, 10 mm, 0.3 mm\nmaterial = G4_Si\nposition = 0 mm, 0 mm, 0.15 mm\nsensitive = true\n'
        meta = dict(kind='silicon', particle='proton', energy_MeV=energy, events=events, material='G4_Si', thickness_mm=.3, size_mm=10)
        scoring = '[scoring]\nevent_edep = true\n'
    write(folder / 'main.ini', '[run]\nmacro = run.mac\n\n[materials]\nfile = materials.ini\n\n[geometry]\ntemplate = hierarchical\nconfig = geometry.ini\n\n'+scoring+'\n'+source)
    write(folder / 'materials.ini', '[nist]\nmaterials = G4_Galactic, G4_Si, G4_SILICON_DIOXIDE, G4_SODIUM_IODIDE\n')
    write(folder / 'geometry.ini', geometry)
    write(folder / 'run.mac', f'/run/initialize\n/run/beamOn {events}\n')
    write(folder / 'scenario.json', json.dumps(meta))
    execution = '1234567890abcdef1234567890abcdef'
    build = dict(git_commit='a'*40, source_fingerprint='b'*64, git_source_state='clean', compiler_id='synthetic_fixture',
                 compiler_version='synthetic_fixture', configuration='synthetic_fixture', geant4_version='synthetic_fixture')
    facts = dict(status='completed', program_exit_code='0', simulation_executed='true', macro_execution_status='completed',
                 summary_write_status='completed', output_failure_status='none', run_count='1', planned_event_count=str(events),
                 actual_completed_event_count=str(events), actual_threads=str(workers), execution_id=execution,
                 output_provenance_schema='g4usim_provenance_v1', build_git_commit=build['git_commit'],
                 source_fingerprint=build['source_fingerprint'], build_git_source_state='clean', geant4_version='synthetic_fixture')
    facts.update(run_summary_schema_version='1', output_csv_schema_version='3', macro_failure_phase='', macro_failure_file='',
                 macro_failure_command='', macro_failure_line='0', macro_failure_code='0', macro_failure_code_available='false',
                 main_config=str((folder/'main.ini').resolve()), materials_file=str((folder/'materials.ini').resolve()),
                 geometry_config=str((folder/'geometry.ini').resolve()), actual_macro_file=str((folder/'run.mac').resolve()))
    write(output / 'run_summary.txt', 'Run Summary\n===========\n\n[Values]\n'+''.join(f'{k} = {v}\n' for k,v in facts.items())+
          f'\n[Runs]\nrun_0_id = 0\nrun_0_planned_events = {events}\nrun_0_completed_events = {events}\n')
    schemas = {'run_summary.txt':('run_summary_v1','process',None,None)}
    if kind == 'device':
        header = 'runID,scorer,quantity,key,name,unit,estimator,n_events,entries,value,mean_per_event,std_error,rel_error,fom_per_s,run_wall_time_s,sum,sum_sq,uncertainty_estimator,uncertainty_status\n'
        lines = []
        for name,key in [('GateOxide','/world_PV#0/GateOxide_PV#0'), ('Active','/world_PV#0/Active_PV#0'), ('Slice0','/world_PV#0/Substrate_PV#0/Slice_PV#0')]:
            for scorer,quant,unit,value in [('dose','weighted_dose','Gy',4),('displacement','ddd_total','MeV/g',8)]:
                value = 0 if zero else value
                state = 'insufficient_events' if events < 2 else ('zero_total' if zero else 'approximate')
                entries = 0 if zero else 1
                rel = 0 if zero else math.sqrt(1-1/events)
                mean = value / events if events else 0
                lines.append(f'0,{scorer},{quant},{key},{name},{unit},total,{events},{entries},{value},{mean},{rel*value},{rel},0,1,{value},{value*value},uncorrected_event_moments_v1,{state}\n')
        write(output/'scorer_statistics.csv', header+''.join(lines))
        schemas['scorer_statistics.csv']=('scorer_statistics_csv_v2','run',0,None)
    else:
        require_values = list(values)
        if len(require_values) != events:
            raise ValueError('fixture event count')
        for worker in range(workers):
            name=f'event_edep_t{worker}.csv'
            write(output/name, 'runID,eventID,raw_edep_MeV,weighted_edep_MeV\n'+''.join(f'0,{i},{v},{v}\n' for i,v in enumerate(require_values) if i % workers == worker))
            schemas[name]=('event_edep_csv_v3','thread',0,worker)
    inputs=[]
    for name,kind_,role in [('main.ini','main_ini','configuration_parse'),('materials.ini','material_ini','material_parse'),
                             ('geometry.ini','geometry_ini','geometry_parse'),('run.mac','macro','recursive_preflight')]+([('si_proton.csv','niel_table','displacement_table_parse')] if kind=='device' else []):
        path=folder/name
        inputs.append(dict(sequence=len(inputs)+1,path=str(path.resolve()),kind=kind_,role=role,capture_method='binary_buffer',
                           reason='',status='recorded',sha256=sha(path),size_bytes=path.stat().st_size))
    records=[]
    for name,(schema,scope,run,thread) in schemas.items():
        path=output/name
        records.append(dict(path=name,schema=schema,execution_id=execution,scope=scope,run_id=run,thread_id=thread,
                            integrity_status='hashed',sha256=sha(path),size_bytes=path.stat().st_size))
    records.append(dict(path='run_metadata.json',schema='run_metadata_json_v1',execution_id=execution,scope='process',run_id=None,
                        thread_id=None,integrity_status='self_reference_excluded',sha256=None,size_bytes=None))
    doc=dict(schema='run_metadata_json_v1',values=facts,runs=[dict(run_id=0,planned_events=events,completed_events=events)],
             generated_files=records,provenance=dict(schema='g4usim_provenance_v1',execution_id=execution,build=build,
             input_coverage='project_readers_observed',input_observation='bytes_read_not_semantic_acceptance',
             input_exclusions=['synthetic_fixture, not native evidence','not science validation'],inputs=inputs))
    save_doc(output,doc)
    return output


class Suite:
    def __init__(self, root, script):
        self.root=root; root.mkdir(parents=True, exist_ok=False)
        self.script=ROOT/script; self.receipts=[]
    def run(self, name, *, mutation=None, expected=0, options=(), generated_particle=None, **kwargs):
        global ACTIVE_CASE
        ACTIVE_CASE = None
        folder=self.root/name; output=fixture(folder, **kwargs)
        if generated_particle is not None:
            generated_device_inputs(output, generated_particle)
        if mutation:
            mutation(output)
        before={str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()}
        args=[sys.executable,'-B',str(self.script),str(output),*options]
        process=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=30)
        (folder/'stdout.txt').write_bytes(process.stdout); (folder/'stderr.txt').write_bytes(process.stderr)
        after={str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()}
        receipt=dict(case=name,fixture_type='synthetic_fixture',command=args,cwd=str(ROOT),exit_code=process.returncode,
                     expected_exit=expected,input_sha256=before,output_sha256=after,environment={'PYTHONOPTIMIZE':os.environ.get('PYTHONOPTIMIZE')})
        receipt['assertions_executed'] = 0
        ACTIVE_CASE = receipt
        self.receipts.append(receipt)
        write(folder/'receipt.json',json.dumps(receipt,indent=2))
        check(process.returncode==expected, f'{name}: expected {expected}, got {process.returncode}: {process.stderr.decode(errors="replace")}')
        report_path=output/('device_report.json' if kwargs.get('kind','device')=='device' else 'detector_report.json')
        if expected not in (0,2):
            check(not report_path.exists(), f'{name}: rejected run published success')
            return None
        check(report_path.is_file(), f'{name}: report missing')
        report=json.loads(report_path.read_bytes())
        check(report['analysis_schema_version']==2 and report['run_status']=='completed',name)
        check(report['scenario_evidence']['backend_read'] is False, name)
        return report
    def finish(self):
        files=['scenarios/semiconductor/analyze_device.py','scenarios/detector_response/analyze_detector.py',
               'scenarios/detector_response/response_physics.py','scenarios/analysis_evidence.py',
               'scripts/test_semiconductor_analysis.py','scripts/test_detector_analysis.py']
        report=dict(fixture_type='synthetic_fixture',cases=self.receipts,assertions_executed=COUNT,
                    source_sha256={name:sha(ROOT/name) for name in files}, python=sys.version,
                    python_executable=sys.executable,python_executable_sha256=sha(Path(sys.executable)))
        report['direct_unit_assertions_executed'] = COUNT - sum(r['assertions_executed'] for r in self.receipts)
        for receipt in self.receipts:
            write(self.root / receipt['case'] / 'receipt.json', json.dumps(receipt, indent=2))
        write(self.root/'report.json',json.dumps(report,indent=2))
        print(f'{len(self.receipts)} synthetic cases; {COUNT} explicit guards plus counted asserts; evidence: {self.root}')


def replace_stat(output, old, new):
    path=output/'scorer_statistics.csv'; write(path,path.read_text().replace(old,new)); rehash(output)


def omit_stats(output, physical=False):
    doc=json.loads((output/'run_metadata.json').read_bytes())
    if physical:
        (output/'scorer_statistics.csv').unlink()
    else:
        doc['generated_files']=[r for r in doc['generated_files'] if r['path']!='scorer_statistics.csv']
        save_doc(output,doc)


def meta_change(output,key,value):
    path=output.parent/'scenario.json'; meta=json.loads(path.read_bytes()); meta[key]=value; write(path,json.dumps(meta))


def generated_device_inputs(output, particle):
    """Real generator bytes plus explicitly synthetic backend evidence, no transport.

    Do not construct the energy sentinel by hand: this regression consumes the
    producer's actual null, single/mixed source blocks and default spectrum bytes.
    """
    import configparser
    folder = output.parent
    generator = ROOT/'scenarios/semiconductor/make_device.py'
    command = [sys.executable, '-B', str(generator), '--out', str(folder), '--particle', particle,
               '--events', '2', '--threads', '1', '--slices', '1', '--lid', 'none', '--beol', 'none',
               '--physics', 'FTFP_BERT']
    process = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=30)
    (folder/'generator-stdout.txt').write_bytes(process.stdout)
    (folder/'generator-stderr.txt').write_bytes(process.stderr)
    write(folder/'generator-receipt.json', json.dumps(dict(command=command, cwd=str(ROOT), exit_code=process.returncode,
        fixture_type='real_generator_inputs_with_synthetic_backend_evidence_no_transport', generator_sha256=sha(generator)), indent=2))
    check(process.returncode == 0, process.stderr.decode(errors='replace'))
    check(json.loads((folder/'scenario.json').read_bytes())['energy_MeV'] is None,
          'actual default producer must emit null')
    # Replace the artificial input observation list; the native summary/statistics
    # remain clearly synthetic_fixture. No backend observation is claimed here.
    doc = json.loads((output/'run_metadata.json').read_bytes())
    doc['provenance']['inputs'] = []
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(folder/'main.ini', encoding='utf-8')
    selected = [(folder/'main.ini', 'main_ini', 'configuration_parse'),
                (folder/'materials.ini', 'material_ini', 'material_parse'),
                (folder/'geometry.ini', 'geometry_ini', 'geometry_parse'),
                (folder/'run.mac', 'macro', 'recursive_preflight')]
    for value in parser['scoring.displacement'].values():
        path = Path(value)
        selected.append(((path if path.is_absolute() else folder/path).resolve(), 'niel_table', 'displacement_table_parse'))
    for section in parser.sections():
        if section == 'source' or section.startswith('source.'):
            value = parser[section].get('spectrum_file')
            if value:
                selected.append((folder/value, 'spectrum', 'source_spectrum_parse'))
    for path, kind, role in selected:
        doc['provenance']['inputs'].append(dict(sequence=len(doc['provenance']['inputs'])+1,
            path=str(path.resolve()), kind=kind, role=role, capture_method='binary_buffer', reason='',
            status='recorded', sha256=sha(path), size_bytes=path.stat().st_size))
    save_doc(output, doc)
    (folder/'si_proton.csv').unlink()  # unused old synthetic table, confined to this new fixture


def main():
    if not __debug__:
        raise SystemExit('optimized mode is rejected: assertion counting requires normal Python')
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0]);parser.add_argument('--evidence-root')
    args=parser.parse_args()
    evidence_parent = os.environ.get('G4USIM_TEST_EVIDENCE_DIR')
    if not args.evidence_root and evidence_parent:
        Path(evidence_parent).mkdir(parents=True, exist_ok=True)
    base=Path(args.evidence_root) if args.evidence_root else Path(tempfile.mkdtemp(prefix='b3-analysis-', dir=os.environ.get('G4USIM_TEST_EVIDENCE_DIR')))/'cases'
    suite=Suite(base,'scenarios/semiconductor/analyze_device.py')
    try:
        r=suite.run('normal')
        e=r['regions']['Active']
        check(e['tid_Gy_per_primary']==2 and e['tid_Gy_cm2']==.5,'hand oracle 4 Gy / 2 primaries x .25 cm2')
        check(e['ddd_MeV_g_per_primary']==4 and e['ddd_MeV_g_cm2']==1,'hand oracle 8 / 2 x .25')
        check(math.isclose(e['tid_rel_error'],math.sqrt(.5),rel_tol=1e-14),'event moment oracle')
        check(math.isclose(e['phi_eq_per_unit_fluence'],1/(95e-27*6.02214076e23/28.0855),rel_tol=1e-14),'reference conversion')
        r=suite.run('explicit_zero',zero=True)
        check(r['analysis_status']=='completed' and r['regions']['Active']['tid_Gy_cm2']==0)
        check(r['regions']['Active']['quantities']['tid_Gy_cm2']['status']=='zero')
        check(r['regions']['Active']['tid_rel_error'] is None)
        r=suite.run('n1_uncertainty',events=1)
        check(r['regions']['Active']['tid_rel_error'] is None and r['regions']['Active']['tid_Gy_cm2']==1)
        r=suite.run('unregistered_stats',mutation=omit_stats,expected=2)
        check(r['analysis_status']=='partial' and r['regions']['Active']['tid_Gy_cm2'] is None)
        csv_text=(base/'unregistered_stats/output/depth_profile.csv').read_text()
        check('unavailable' in csv_text and ',,' in csv_text,'CSV null must be empty')
        def missing_one(o):
            p=o/'scorer_statistics.csv'; lines=p.read_text().splitlines(); write(p,'\n'.join(x for x in lines if not x.startswith('0,dose,weighted_dose,/world_PV#0/Active_PV#0,'))+'\n');rehash(o)
        r=suite.run('missing_quantity',mutation=missing_one,expected=2)
        check(r['regions']['Active']['tid_Gy_cm2'] is None and r['regions']['Active']['ddd_MeV_g_cm2']==1)
        suite.run('registered_stats_missing',mutation=lambda o:omit_stats(o,True),expected=1)
        for name,old,new in [('unit',',Gy,',',MeV,'),('run_id','0,dose,','1,dose,'),('estimator',',total,',',ratio,'),
                             ('events',',total,2,',',total,3,'),('negative_count',',total,2,1,',',total,2,-1,'),
                             ('nan',',4,2.0,',',nan,2.0,'),('infinity',',4,2.0,',',inf,2.0,'),
                             ('uncertainty',',approximate',',zero_total')]:
            suite.run('bad_'+name,mutation=lambda o,a=old,b=new:replace_stat(o,a,b),expected=1)
        def duplicate(o):
            p=o/'scorer_statistics.csv';write(p,p.read_text()+p.read_text().splitlines()[1]+'\n');rehash(o)
        suite.run('duplicate_stat',mutation=duplicate,expected=1)
        for name,key,value in [('failed','status','failed'),('aborted','status','aborted'),('cancelled','status','cancelled'),
                               ('exit','program_exit_code','1'),('macro_after_full_run','macro_execution_status','failed'),
                               ('summary_write','summary_write_status','failed'),('output_failed','output_failure_status','failed'),
                               ('missing_run_count','run_count',''),('multi_run','run_count','2'),('zero_runs','run_count','0'),
                               ('zero_total_events','planned_event_count','0'),('total_mismatch','actual_completed_event_count','1'),
                               ('build_mismatch','source_fingerprint','c'*64),('worker_unknown','actual_threads','unknown')]:
            suite.run('admission_'+name,mutation=lambda o,k=key,v=value:fact(o,k,v),expected=1)
        def text_conflict(o):
            p=o/'run_summary.txt';write(p,p.read_text().replace('status = completed','status = failed'));rehash(o)
        suite.run('text_metadata_conflict',mutation=text_conflict,expected=1)
        def duplicate_fact(o):
            p=o/'run_summary.txt';write(p,p.read_text().replace('[Values]','[Values]\nstatus = completed'));rehash(o)
        suite.run('duplicate_fact',mutation=duplicate_fact,expected=1)
        def duplicate_section(o):
            p=o/'run_summary.txt';write(p,p.read_text()+'\n[Values]\n');rehash(o)
        suite.run('duplicate_section',mutation=duplicate_section,expected=1)
        def no_metadata(o): (o/'run_metadata.json').unlink()
        suite.run('legacy_rejected',mutation=no_metadata,expected=1)
        def corrupt(o):
            p=o/'scorer_statistics.csv';p.write_bytes(p.read_bytes()+b'\n')
        suite.run('hash_tamper_without_rehash',mutation=corrupt,expected=1)
        suite.run('scenario_area',mutation=lambda o:meta_change(o,'source_area_cm2',1),expected=1)
        def layer(o):
            p=o.parent/'scenario.json';m=json.loads(p.read_bytes());m['layers'][0]['material']='G4_Si';write(p,json.dumps(m))
        suite.run('scenario_material',mutation=layer,expected=1)
        def thickness(o):
            p=o.parent/'scenario.json';m=json.loads(p.read_bytes());m['layers'][1]['thickness_mm']=.02;write(p,json.dumps(m))
        suite.run('scenario_thickness',mutation=thickness,expected=1)
        def slices(o):
            p=o.parent/'scenario.json';m=json.loads(p.read_bytes());m['slices'][0]['copy']=1;write(p,json.dumps(m))
        suite.run('scenario_slices',mutation=slices,expected=1)
        for filename in ('main.ini','materials.ini','geometry.ini','si_proton.csv'):
            def changed(o,n=filename):
                p=o.parent/n;write(p,p.read_text()+'\n# changed actual input\n')
            suite.run('changed_'+filename,mutation=changed,expected=1)
        r=suite.run('flux_unbound',mutation=lambda o:meta_change(o,'sampled_integral_flux_cm2_s',{'proton':3}),expected=2)
        check(r['regions']['Active']['tid_Gy_per_year'] is None and r['regions']['Active']['tid_Gy_cm2']==.5)
        # Relocation retains original historical paths and exact input bytes.
        def relocation(o):
            d=json.loads((o/'run_metadata.json').read_bytes())
            for row in d['provenance']['inputs']: row['path']='Z:/old-unavailable-location/'+Path(row['path']).name
            save_doc(o,d)
        suite.run('relocated_same_bytes',mutation=relocation)
        def spectrum(o):
            p=o.parent/'main.ini';write(p,p.read_text().replace('energy = 50 MeV', 'energy_type = histogram\nspectrum_file = spectrum_proton.csv'))
            common_text='# histogram from synthetic.txt: weight = integral flux F(E_low) - F(E_high) [cm-2 s-1]\ne_low_MeV,e_high_MeV,weight\n1,2,1\n2,3,2\n'
            p=o.parent/'spectrum_proton.csv';write(p,common_text)
            meta_change(o,'energy_MeV',0);meta_change(o,'sampled_integral_flux_cm2_s',{'proton':3})
            d=json.loads((o/'run_metadata.json').read_bytes())
            d['provenance']['inputs'].append(dict(sequence=len(d['provenance']['inputs'])+1,path=str(p.resolve()),kind='spectrum',
                role='source_spectrum_parse',capture_method='binary_buffer',reason='',status='recorded',sha256=sha(p),size_bytes=p.stat().st_size))
            save_doc(o,d);rehash(o,inputs=True)
        r=suite.run('bound_spectrum_rate',mutation=spectrum)
        check(r['regions']['Active']['tid_Gy_per_year']==.5*3*31557600,'annual rate hand oracle')
        for particle in ('proton', 'e-', 'mixed'):
            r=suite.run('actual_generator_null_'+particle.replace('-', 'minus'), generated_particle=particle)
            check(r['scenario']['energy_MeV'] is None and r['analysis_status']=='completed', 'actual generator null accepted')
            spectra=[x for x in r['input_binding'] if x['kind']=='spectrum' and x['role']=='source_spectrum_parse']
            check(len(spectra)==(2 if particle=='mixed' else 1), 'actual spectra bound by bytes and role')
            flux=sum(r['scenario']['sampled_integral_flux_cm2_s'].values())
            check(math.isclose(r['regions']['Active']['tid_Gy_per_year'],.5*flux*31557600,rel_tol=1e-14), 'real generated flux scale oracle')
        def unset_spectrum(o, energy=None):
            spectrum(o);meta_change(o,'energy_MeV',energy)
        suite.run('bound_spectrum_null',mutation=unset_spectrum)
        suite.run('null_with_mono_rejected',mutation=lambda o:meta_change(o,'energy_MeV',None),expected=1)
        for label, value in (('false',False),('empty_string',''),('empty_list',[]),('empty_object',{}),('numeric_string','0')):
            suite.run('bad_spectrum_energy_'+label,mutation=lambda o,v=value:unset_spectrum(o,v),expected=1)
        def conflicting_mono(o):
            unset_spectrum(o);p=o.parent/'main.ini';write(p,p.read_text().replace('energy_type = histogram','energy = 50 MeV\nenergy_type = histogram'));rehash(o,inputs=True)
        suite.run('null_histogram_with_mono_conflict',mutation=conflicting_mono,expected=1)
        suite.run('actual_threads_zero',mutation=lambda o:fact(o,'actual_threads','0'),expected=1)
        def spectrum_changed(o):
            spectrum(o);p=o.parent/'spectrum_proton.csv';write(p,p.read_text().replace('2,3,2','2,3,3'))
        suite.run('spectrum_bytes_changed',mutation=spectrum_changed,expected=1)
        def spectrum_scale(o):
            spectrum(o);meta_change(o,'sampled_integral_flux_cm2_s',{'proton':4})
        suite.run('spectrum_metadata_scale',mutation=spectrum_scale,expected=1)
        for key,value in [('run_summary_schema_version','2'),('output_csv_schema_version','2'),('macro_failure_phase','execution')]:
            suite.run('bad_format_'+key,mutation=lambda o,k=key,v=value:fact(o,k,v),expected=1)
        def doc_mutate(o, action):
            d=json.loads((o/'run_metadata.json').read_bytes());action(d);save_doc(o,d)
        suite.run('artifact_execution_mismatch',mutation=lambda o:doc_mutate(o,lambda d:d['generated_files'][0].update(execution_id='f'*32)),expected=1)
        suite.run('artifact_scope_mismatch',mutation=lambda o:doc_mutate(o,lambda d:d['generated_files'][1].update(scope='thread',thread_id=0)),expected=1)
        suite.run('artifact_path_escape',mutation=lambda o:doc_mutate(o,lambda d:d['generated_files'][1].update(path='../scorer_statistics.csv')),expected=1)
        suite.run('wrong_stats_schema',mutation=lambda o:doc_mutate(o,lambda d:d['generated_files'][1].update(schema='unknown')),expected=1)
        suite.run('input_role_mismatch',mutation=lambda o:doc_mutate(o,lambda d:d['provenance']['inputs'][1].update(role='unrelated')),expected=1)
        suite.run('same_total_wrong_run_count',mutation=lambda o:doc_mutate(o,lambda d:d['runs'].append(dict(run_id=1,planned_events=0,completed_events=0))),expected=1)
        suite.run('metadata_run_incomplete',mutation=lambda o:doc_mutate(o,lambda d:d['runs'][0].update(completed_events=1)),expected=1)
        def missing_count(o):
            d=json.loads((o/'run_metadata.json').read_bytes());del d['values']['run_count'];save_doc(o,d)
            p=o/'run_summary.txt';write(p,p.read_text().replace('run_count = 1\n',''));rehash(o)
        suite.run('run_count_absent',mutation=missing_count,expected=1)
        # A zero-event, fully rehashed directory is semantically invalid even if totals agree.
        suite.run('zero_event_run',events=0,zero=True,expected=1)
        def region_missing(o):
            p=o/'scorer_statistics.csv';write(p,'\n'.join(line for line in p.read_text().splitlines() if '/Active_PV#0,' not in line)+'\n');rehash(o)
        r=suite.run('region_missing',mutation=region_missing,expected=2)
        check(r['regions']['Active']['tid_Gy_cm2'] is None and r['regions']['GateOxide']['tid_Gy_cm2']==.5)
        def tracks(o, inside=8, outside=2):
            name='displacement_volume_summary_t0.csv'
            write(o/name,'runID,volume_path,volume_name,particle,niel_table,volume_mm3,track_length_mm,out_of_range_track_length_mm,ddd_MeV_g,ddd_sum_sq_MeV2_g2,n_events\n'
                  f'0,/world_PV#0/Active_PV#0,Active,proton,si_proton.csv,1,{inside},{outside},8,64,2\n')
            d=json.loads((o/'run_metadata.json').read_bytes())
            d['generated_files'].append(dict(path=name,schema='displacement_volume_csv_v1',scope='thread',run_id=0,thread_id=0,
                execution_id=d['provenance']['execution_id'],integrity_status='hashed',sha256=sha(o/name),size_bytes=(o/name).stat().st_size))
            save_doc(o,d)
        r=suite.run('track_range_oracle',mutation=tracks)
        check(r['out_of_range_fraction']['proton']==.2,'original 2 / (8+2) track fraction')
        r=suite.run('zero_track_denominator',mutation=lambda o:tracks(o,0,0))
        check(r['out_of_range_fraction']['proton'] is None)
        r=suite.run('missing_worker_track',workers=2,mutation=tracks)
        check(r['out_of_range_fraction']['proton'] is None and r['out_of_range_quantities']['proton']['reason']=='incomplete_worker_track_evidence')
        suite.run('overflow_track_sum',mutation=lambda o:tracks(o,1e308,1e308),expected=1)
        # Publisher exception rollback and post-verification byte-race checks are
        # direct synthetic IO checks, kept separately from CLI/native evidence.
        global ACTIVE_CASE
        ACTIVE_CASE = None
        sys.path.insert(0, str(ROOT/'scenarios'))
        import analysis_evidence as ae
        directory=base/'publication_fixture';directory.mkdir()
        write(directory/'a.csv','old csv');write(directory/'a.json','old json')
        original=ae.os.replace; calls=0
        def fail_once(src,dst):
            nonlocal calls
            calls+=1
            if calls==2:
                raise OSError('synthetic publication failure on JSON replacement')
            return original(src,dst)
        ae.os.replace=fail_once
        try:
            rejected=False
            try:
                ae.publish(directory, {'a.csv':b'new csv','a.json':b'new json'})
            except OSError:
                rejected=True
            check(rejected and (directory/'a.csv').read_bytes()==b'old csv' and (directory/'a.json').read_bytes()==b'old json',
                  'failed publication must restore earlier pair')
            check(sorted(p.name for p in directory.iterdir())==['a.csv','a.json'],'temporary files cleaned')
        finally:
            ae.os.replace=original
        race=fixture(base/'byte_race')
        original_evidence=ae.output_evidence
        def raced(path):
            result=original_evidence(path)
            target=race/'scorer_statistics.csv';target.write_bytes(target.read_bytes()+b'\n')
            return result
        ae.output_evidence=raced
        try:
            rejected=False
            try: ae.AnalysisEvidence(race)
            except ValueError as error:
                rejected='changed during consumption' in str(error)
            check(rejected,'verified-then-reread bytes must be compared again')
        finally:
            ae.output_evidence=original_evidence
    finally:
        suite.finish()


if __name__=='__main__':
    main()

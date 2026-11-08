"""Finite synthetic B4 numerical/admission regression, without Geant4 or fitting."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import test_semiconductor_analysis as common
from test_semiconductor_analysis import Suite, fact, rehash, save_doc, write


def check(condition, message='check failed'):
    # Keep the assert in this test's own source for test_assert_probe's file scope.
    if not condition:
        raise AssertionError(message)
    assert condition, message
    common.COUNT += 1
    if common.ACTIVE_CASE is not None:
        common.ACTIVE_CASE['assertions_executed'] += 1


common.check = check

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scenarios/detector_response'))
import analyze_detector as detector
import response_physics as rp


def main():
    if not __debug__:
        raise SystemExit('optimized mode is rejected: assertion counting requires normal Python')
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0]);parser.add_argument('--evidence-root')
    args=parser.parse_args()
    evidence_parent = os.environ.get('G4USIM_TEST_EVIDENCE_DIR')
    if not args.evidence_root and evidence_parent:
        Path(evidence_parent).mkdir(parents=True, exist_ok=True)
    base=Path(args.evidence_root) if args.evidence_root else Path(tempfile.mkdtemp(prefix='b4-analysis-', dir=os.environ.get('G4USIM_TEST_EVIDENCE_DIR')))/'cases'
    suite=Suite(base,'scenarios/detector_response/analyze_detector.py')
    try:
        # Independent bin-crossing arithmetic: peak=4, half=2, centres 1.5/2.5/3.5,
        # crossings at centres 1.5 and 3.5 => width 2, peak position 2.5.
        check(detector.fwhm_of([0,2,4,2,0],1)==(2.,2.5),'complete crossing interpolation oracle')
        for counts in ([],[0,0],[4,2,0],[0,2,4],[4]):
            check(detector.fwhm_of(counts,1)[0] is None,'empty/zero/truncated FWHM')
        check(rp.half_sample_mode([]) is None)
        check(rp.half_sample_mode([1])==1 and rp.half_sample_mode([1,3])==2)
        check(rp.half_sample_mode([1,2,9])==1.5 and rp.half_sample_mode([1,5,9])==5)
        check(rp.half_sample_mode([1,2,3,100])==1.5,'fixed shortest-half tie behaviour')
        check(rp.mode_with_error([1,3])==(2,None),'no adaptive batch count')
        # 20 batches of size 2, [1,1],[2,2],...,[20,20]. Sample batch variance 35,
        # variance of mean=35/20, SEM=sqrt(1.75); earliest shortest halves end [1,1,2].
        fixed=[float(v) for v in range(1,21) for _ in range(2)]
        mode,error=rp.mode_with_error(fixed)
        check(mode==1 and math.isclose(error,math.sqrt(1.75),rel_tol=1e-14),'original 20 batch oracle')
        # Positive step at bin 400 over otherwise empty windows => unchanged edge 400 keV.
        counts=[0]*800;counts[399]=10
        edge,reason=detector.compton_measurement(counts,.001,.662)
        check(edge==.4 and reason=='','normal Compton step oracle')
        for energy in (.02,.03,.05):
            for n in (1,2):
                for explicit in (False,True):
                    for smear in (False,True):
                        options=(['--bin','2'] if explicit else [])+(['--fwhm','0,0.04,0'] if smear else [])
                        name=f'gamma_{energy}_{n}_bin{int(explicit)}_smear{int(smear)}'
                        r=suite.run(name,kind='gamma',energy=energy,events=n,values=[0]*n,options=options)
                        check(r['detection_efficiency_intrinsic']==0 and r['fep_efficiency_intrinsic']==0)
                        check(r['peak_to_total'] is None and r['compton_edge_MeV'] is None)
                        check(r['quantities']['detection_efficiency_intrinsic']['status']=='zero')
                        check(r['quantities']['compton_edge_klein_nishina_MeV']['basis']=='model_prediction')
                        if smear:
                            check(r['photopeak_fwhm_MeV'] is None and r['photopeak_position_MeV'] is None)
                        # A nonzero event/FEP counterpart distinguishes sparse zero from
                        # low-count unavailable shape at the same energy/bin/seed.
                        r=suite.run(name+'_fep',kind='gamma',energy=energy,events=n,values=[energy]*n,options=options)
                        check(r['detection_efficiency_intrinsic']==1 and r['fep_efficiency_intrinsic']==1)
                        check(r['compton_edge_MeV'] is None)
                        if smear:
                            check(r['photopeak_fwhm_MeV'] is None if n==1 else r['photopeak_fwhm_MeV'] is not None)
        # Exact peak fixtures preserve the n-1 sample variance, independent of random sampling:
        # zero-width GEB gives .6615 and .6625; mean .662, sum squared=5e-7.
        for n,values in [(0,[0,0]),(1,[.662,0]),(2,[.6615,.6625])]:
            r=suite.run(f'peak_n{n}',kind='gamma',energy=.662,events=2,values=values,options=['--fwhm','0,0,0'])
            check(r['quantities']['photopeak_position_MeV']['sample_count']==n)
            if n<2:
                check(r['photopeak_fwhm_MeV'] is None)
            else:
                check(math.isclose(r['photopeak_fwhm_MeV'],2.3548*math.sqrt(5e-7),rel_tol=1e-12),'n-1 sample width oracle')
            check(r['photopeak_position_MeV'] is None if n==0 else math.isclose(r['photopeak_position_MeV'],.662,rel_tol=1e-15))
        r=suite.run('si_no_positive',kind='silicon',energy=50,events=2,values=[0,0])
        check(r['detected_fraction']==0 and r['quantities']['detected_fraction']['status']=='zero')
        check(all(r[k] is None for k in ('mpv_MeV','mpv_error_MeV','mean_MeV','fwhm_MeV')))
        check('0,0.0005,1,' in (base/'si_no_positive/output/pulse_height.csv').read_text(),'keep real zero deposit spectrum')
        r=suite.run('peak_two_identical',kind='gamma',events=2,values=[.662,.662],options=['--fwhm','0,0,0'])
        check(r['photopeak_fwhm_MeV']==0 and r['quantities']['photopeak_fwhm_MeV']['basis']=='sample_estimate',
              'zero sample width does not certify instrument resolution')
        r=suite.run('seeded_peak_oracle',kind='gamma',events=2,values=[.662,.662],options=['--fwhm','.01,0,0','--seed','1'])
        z1,z2=1.2881847531554629,1.449445608699771
        check(math.isclose(r['photopeak_position_MeV'],.662+.01/2.3548*(z1+z2)/2,rel_tol=1e-14),'fixed seed position oracle')
        check(math.isclose(r['photopeak_fwhm_MeV'],.01*abs(z1-z2)/math.sqrt(2),rel_tol=1e-12),'fixed seed sample FWHM oracle')
        for n in (1,2,19,20,40):
            r=suite.run(f'si_positive_{n}',kind='silicon',energy=50,events=n,values=[.01]*n)
            check(r['mpv_MeV']==.01 and math.isclose(r['mean_MeV'],.01,rel_tol=1e-14))
            check(r['mpv_error_MeV'] is None if n<20 else abs(r['mpv_error_MeV'])<1e-17,
                  '20 fixed batches only; constant-data SEM is zero up to floating summation')
        # A nontrivial fixed spectrum retains the ordinary efficiency and units.
        r=suite.run('normal_efficiency',kind='gamma',energy=.662,events=4,values=[0,.001,.1,.662],workers=2)
        check(r['detection_efficiency_intrinsic']==.5 and r['fep_efficiency_intrinsic']==.25 and r['peak_to_total']==.5)
        check(math.isclose(r['detection_efficiency_absolute'],.5*(1-math.cos(math.radians(10)))/2,rel_tol=1e-14))
        r=suite.run('idle_worker',kind='gamma',energy=.662,events=1,values=[.1],workers=2)
        check(r['detection_efficiency_intrinsic']==1)
        for flag,value in [('--bin','0'),('--bin','-1'),('--bin','nan'),('--bin','inf'),
                           ('--fwhm','0,1'),('--fwhm','0,nan,0'),('--fwhm','-1,0,0'),('--fwhm','0,1,-100')]:
            suite.run('invalid_option_'+str(len(suite.receipts)),kind='gamma',events=2,values=[0,.662],options=[flag+'='+value],expected=1)
        def event_change(o,old,new):
            p=o/'event_edep_t0.csv';write(p,p.read_text().replace(old,new));rehash(o)
        for name,old,new in [('duplicate','0,1,','0,0,'),('wrong_run','0,1,','1,1,'),
                             ('negative','0.2,0.2','-0.2,0.2'),('nan','0.2,0.2','nan,0.2'),('inf','0.2,0.2','inf,0.2'),
                             ('out_of_range','0,1,','0,2,')]:
            suite.run('event_'+name,kind='gamma',mutation=lambda o,a=old,b=new:event_change(o,a,b),expected=1)
        def missing_row(o):
            p=o/'event_edep_t0.csv';write(p,'\n'.join(p.read_text().splitlines()[:-1])+'\n');rehash(o)
        suite.run('missing_event',kind='gamma',mutation=missing_row,expected=1)
        for name,key,value in [('post_run_failed','status','failed'),('post_run_macro_failed','macro_execution_status','failed'),
                               ('nonzero_exit','program_exit_code','1'),('incomplete','actual_completed_event_count','1')]:
            suite.run(name,kind='gamma',mutation=lambda o,k=key,v=value:fact(o,k,v),expected=1)
        def wrong_energy(o):
            common.meta_change(o,'energy_MeV',1)
        suite.run('unbound_energy',kind='gamma',mutation=wrong_energy,expected=1)
        def wrong_cone(o): common.meta_change(o,'cone_fraction_of_4pi',.5)
        suite.run('unbound_cone',kind='gamma',mutation=wrong_cone,expected=1)
        def corrupt(o):
            p=o/'event_edep_t0.csv';p.write_bytes(p.read_bytes()+b'\n')
        suite.run('hash_tamper_without_rehash',kind='gamma',mutation=corrupt,expected=1)
        def missing_worker(o):
            d=json.loads((o/'run_metadata.json').read_bytes());d['generated_files']=[r for r in d['generated_files'] if r['path']!='event_edep_t1.csv'];save_doc(o,d)
        suite.run('unregistered_idle_worker',kind='gamma',events=1,values=[.1],workers=2,mutation=missing_worker,expected=1)
        suite.run('actual_threads_zero',kind='gamma',mutation=lambda o:fact(o,'actual_threads','0'),expected=1)
    finally:
        suite.finish()


if __name__=='__main__':
    main()

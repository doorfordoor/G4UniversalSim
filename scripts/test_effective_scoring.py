#!/usr/bin/env python3
"""2C scoring projection/runtime gate; optional independent NIEL component gate."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
COMPONENT=r'''
#include "Scoring/NielTable.hh"
#include <fstream>
#include <iostream>
#include <cmath>
int main(int argc,char** argv) {
 if(argc!=2)return 10;
 auto table=NielTable::Load(argv[1]);
 auto hash=table->GetInputSha256();
 {std::ofstream replacement(argv[1],std::ios::binary);replacement<<"replaced after parse";}
 if(table->GetInputSha256()!=hash || table->Size()!=2)return 11;
 double result=0;if(!table->Evaluate(std::sqrt(10.0),result))return 12;
 if(std::abs(result-10.0)>1e-10)return 13;
 if(table->Evaluate(0.1,result) || table->Evaluate(11.0,result))return 14;
 std::cout<<hash<<"\n"<<table->Energies()[0]<<","<<table->Energies()[1]<<"\n"
          <<table->Values()[0]<<","<<table->Values()[1]<<"\n";
}
'''

def component(headers):
    assert headers and (headers/'G4SystemOfUnits.hh').is_file(), 'Pass --geant4-include with the Geant4 headers directory'
    compiler=os.environ.get('CXX') or shutil.which('g++')
    assert compiler, 'A C++17 compiler is required'
    with tempfile.TemporaryDirectory(prefix='g4usim-niel-component-') as temp:
        work=Path(temp)
        source=work/'component.cc';source.write_text(COMPONENT,encoding='utf-8')
        content=b'\xef\xbb\xbfenergy_MeV,niel_MeV_cm2_g\r\n1,1\r\n10,100\r\n'
        table=work/'niel.csv';table.write_bytes(content)
        executable=work/('component.exe' if os.name=='nt' else 'component')
        args=[compiler,'-std=c++17','-I'+str(ROOT/'include'),'-I'+str(headers),
              str(source),str(ROOT/'src/Scoring/NielTable.cc'),str(ROOT/'src/Config/InputProvenance.cc'),
              str(ROOT/'src/Utils/StringUtils.cc'),'-o',str(executable)]
        built=subprocess.run(args,capture_output=True,text=True,timeout=90)
        assert built.returncode==0,built.stdout+built.stderr
        ran=subprocess.run([str(executable),str(table)],capture_output=True,text=True,timeout=20)
        assert ran.returncode==0,ran.stdout+ran.stderr
        lines=ran.stdout.splitlines()
        assert lines==[hashlib.sha256(content).hexdigest(),'1,10','1,100'],lines
        assert table.read_bytes()==b'replaced after parse'
        print('PASS: independent NIEL exact BOM/CRLF bytes, stable digest after replacement, nodes and interpolation')


def backend(executable):
    assert executable and executable.is_file(),'Set G4USIM_EXE or --executable to the newly built candidate'
    with tempfile.TemporaryDirectory(prefix='g4usim-effective-scoring-') as temp:
        work=Path(temp)
        niel=work/'niel.csv'
        niel.write_bytes(b'\xef\xbb\xbfenergy_MeV,niel_MeV_cm2_g\r\n0.1,1\r\n100,10\r\n')
        digest=hashlib.sha256(niel.read_bytes()).hexdigest()
        geometry=work/'geometry.ini'
        geometry.write_text('[world]\nshape=box\nsize=1 m,1 m,1 m\nmaterial=G4_Galactic\n'
                            '[volume.Target]\nparent=world\nshape=box\nsize=20 mm,20 mm,20 mm\nmaterial=G4_Si\nsensitive=true\n',encoding='utf-8')
        base='[run]\nthreads=1\n[geometry]\ntemplate=hierarchical\nconfig='+geometry.as_posix()+\
             '\n[source]\nparticle=proton\nenergy=2 MeV\nposition_type=point\nposition=0,0,-9 mm\ndirection=+z\n'
        scoring='[scoring]\nenabled=true\nhits=false\nevent_edep=true\nedep=true\nlet=true\ndose=true\nfluence=true\ndisplacement=true\n'+\
                '[scoring.let]\nparticles=proton\n[scoring.displacement]\nPrOtOn='+niel.as_posix()+\
                '\n[scoring.edep]\nbins=17\nmin=0 MeV\nmax=4 MeV\nraw_histogram=false\nweighted_histogram=true\n'+\
                '[output]\ntrajectories=1\ntrajectory_min_energy=0.1 MeV\ntrajectory_max_points=100\n'
        mesh='[scoring.mesh.Tube]\nshape=cylinder\nsize=3 mm,7 mm\nbins=1,1,1\n'+\
             '[scoring.mesh.Tube.Edep]\ntype=energyDeposit\nunit=MeV\nparticles=proton\nenergy_min=0.1 MeV\nenergy_max=10 MeV\n'
        sequence=0
        def run(extra='',commands='',inspect=False,scoring_text=None):
            nonlocal sequence
            sequence+=1;directory=work/str(sequence);directory.mkdir()
            output=directory/'output';ini=directory/'main.ini'
            ini.write_text(base+(scoring if scoring_text is None else scoring_text)+mesh+extra,encoding='utf-8')
            macro=directory/'run.mac';macro.write_text(commands,encoding='utf-8')
            args=[str(executable),'--config',str(ini),'--output',str(output),'--macro',str(macro)]
            if inspect:args.extend(['--dump-effective-config','-'])
            result=subprocess.run(args,cwd=directory,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=150)
            assert result.returncode==0,result.stdout+result.stderr
            if inspect:return json.loads(result.stdout)
            documents=[json.loads(path.read_text(encoding='utf-8')) for path in output.glob('effective_config_*.json')]
            assert documents
            return documents
        ignored=run(inspect=True,scoring_text='[scoring.edep]\nbins=31\nraw_histogram=false\n[output]\ntrajectories=2\n')
        ignored_fields={field['path']:field for field in ignored['fields']}
        assert ignored_fields['/scoring/objects/edep_histogram/bins']['resolved']!=31
        assert ignored_fields['/scoring/objects/edep/raw_histogram']['resolved'] is True
        assert ignored_fields['/trajectories/events']['resolved']==2
        assert not any(origin.get('kind')=='main_ini' for origin in ignored_fields['/scoring/objects/edep_histogram/bins']['origins'])
        initial=run(inspect=True)
        fields={field['path']:field for field in initial['fields']}
        assert fields['/scoring/objects/edep_histogram/bins']['resolved']==17
        assert fields['/scoring/objects/weighted_edep_histogram/bins']['resolved']==17
        niel_path='/scoring/objects/niel:proton/'
        assert fields[niel_path+'input_sha256']['resolved']==digest
        assert fields[niel_path+'data']['resolved']==[[0.1,1],[100,10]]
        assert sum(origin.get('input_sha256')==digest for origin in fields[niel_path+'file']['origins'])==1
        docs=run(commands='/AIHL/scoring/edep true\n/AIHL/scoring/edep true\n/run/initialize\n/run/beamOn 2\n/run/beamOn 2\n')
        worker=[doc for doc in docs if doc['stage']=='run_begin' and doc['role'] in ('worker','sequential')]
        assert {doc['run_id'] for doc in worker}=={0,1}
        for doc in worker:
            current={field['path']:field for field in doc['fields']}
            for key in ('edep','let','dose','fluence','displacement'):
                assert current['/scoring/'+key]['application_status']=='applied',(key,current['/scoring/'+key])
            assert current['/scoring/objects/edep/raw_histogram']['application_status']=='applied'
            assert current['/scoring/objects/let/particles']['application_status']=='applied'
            assert current['/trajectories/events']['application_status']=='applied'
            assert current['/scoring/objects/edep_histogram/bins']['application_status']!='applied'
            assert current[niel_path+'file']['application_status']!='applied'
            assert sum(origin.get('kind')=='macro' for origin in current['/scoring/edep']['origins'])==2
            assert sum(origin.get('input_sha256')==digest for origin in current[niel_path+'file']['origins'])==1
            assert current['/mesh/objects/Tube/size']['resolved']==[3,7]
            size_receipts=[r for r in doc['evidence'] if r.get('path')=='/mesh/objects/Tube/size']
            assert any(r.get('observed')==[3,7] for r in size_receipts),size_receipts
            assert current['/mesh/objects/Tube~1quantities~1Edep/type']['application_status']=='applied'
            for name in ('particles','energy_min','energy_max'):
                assert current['/mesh/objects/Tube~1quantities~1Edep/'+name]['application_status']!='applied'
        suppressed=run(extra='[modules]\nscoring=auto\n[phase_space]\nvolume=Target_PV\nkill=false\n',inspect=True,scoring_text='[scoring]\nenabled=false\n[output]\ntrajectories=1\n')
        off={field['path']:field for field in suppressed['fields']}
        assert off['/scoring/enabled']['resolved'] is False
        assert off['/trajectories/events']['resolved']==1
        assert off['/phase_space/volume']['resolved']=='Target_PV'
        only_trajectory_off=run(extra='[output]\ntrajectories=0\n[modules]\ntrajectories=off\n',inspect=True)
        off={field['path']:field for field in only_trajectory_off['fields']}
        assert off['/scoring/enabled']['resolved'] is True and off['/trajectories/events']['resolved']==0
        print('PASS: scoring projection, exact NIEL provenance, independent typed scorers, same-value command origins, cylindrical mesh, module boundaries')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--component',action='store_true')
    parser.add_argument('--geant4-include',type=Path)
    parser.add_argument('--executable',default=os.environ.get('G4USIM_EXE'))
    args=parser.parse_args()
    if args.component:component(args.geant4_include)
    else:backend(Path(args.executable).resolve() if args.executable else None)
if __name__=='__main__':main()

"""Optional module policies use the real consumer, not just enum validation."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    exe = Path(os.environ['G4USIM_EXE']).resolve()
    with tempfile.TemporaryDirectory(prefix='g4usim-modules-') as temporary:
        work = Path(temporary)
        def inspect(name, body, okay=True):
            config=work/(name+'.ini'); output=work/(name+'.json')
            config.write_text(body,encoding='utf-8')
            process=subprocess.run([str(exe),'--config',str(config),'--dump-effective-config',str(output)],
                cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
            assert (process.returncode==0)==okay, process.stdout+process.stderr
            if okay:
                snapshot=json.loads(output.read_text(encoding='utf-8'))
                assert not snapshot['execution_performed']
                return {field['path']:field for field in snapshot['fields']}
            assert not output.exists()
            return process.stdout+process.stderr
        legacy=inspect('legacy','[source]\nparticle=gamma\nenergy=1 MeV\n')
        assert legacy['/scoring/enabled']['resolved'] is True
        assert 'requested' not in legacy['/modules/scoring']
        auto=inspect('auto','[modules]\nscoring=auto\nbiasing=auto\nfield=auto\ntrajectories=auto\n')
        assert auto['/scoring/enabled']['resolved'] is False
        for name in ('scoring','biasing','field','trajectories'):
            assert auto[f'/modules/objects/{name}/enabled']['resolved'] is False
            assert auto[f'/modules/{name}']['requested']=='auto'
        off=inspect('off','[modules]\nscoring=off\nbiasing=off\ntrajectories=off\nfield=off\n')
        assert off['/scoring/enabled']['resolved'] is False
        assert off['/scoring/event_edep']['resolved'] is False
        assert off['/trajectories/events']['resolved']==0
        requests={
            'scoring':'[scoring]\nenabled=true\nevent_edep=true\n',
            'biasing':'[biasing.xs.proton.hIoni]\nfactor=2\nvolumes=Target\n',
            'field':'[field]\nmagnetic=0,0,1 T\n',
            'trajectories':'[output]\ntrajectories=2\n',
        }
        for name,request in requests.items():
            assert 'requires' in inspect('missing-'+name,f'[modules]\n{name}=on\n',False)
            for mode in ('on','auto'):
                fields=inspect(name+'-'+mode,f'[modules]\n{name}={mode}\n'+request)
                assert fields[f'/modules/objects/{name}/enabled']['resolved'] is True
            # Biasing off + enabled false is inactive legacy configuration;
            # explicitly enabling the hook makes its request unambiguous.
            active=request+('[biasing]\nenabled=true\n' if name=='biasing' else '')
            assert 'conflicts' in inspect(name+'-off',f'[modules]\n{name}=off\n'+active,False)
        for mode in ('on','auto'):
            assert 'requires complete' in inspect('bias-empty-'+mode,f'[modules]\nbiasing={mode}\n[biasing]\nenabled=true\n',False)
            assert 'conflicts' in inspect('bias-disabled-'+mode,f'[modules]\nbiasing={mode}\n[biasing]\nenabled=false\n'+requests['biasing'],False)
            assert 'conflicts' in inspect('wrapper-disabled-'+mode,f'[modules]\nbiasing={mode}\n[physics]\nbiasing=false\n'+requests['biasing'],False)
            assert 'conflicts' in inspect('scorer-disabled-'+mode,f'[modules]\nscoring={mode}\n[scoring]\nenabled=false\nevent_edep=true\n',False)
            legacy_rules=inspect('legacy-rules-'+mode,f'[modules]\nbiasing={mode}\n[biasing.xs]\nparticles=proton\nprocesses=hIoni\nfactor=2\nvolumes=Target\n')
            assert legacy_rules['/biasing/enabled']['resolved'] is True
            mesh='[scoring]\nenabled=false\n[scoring.mesh.Grid]\nshape=box\nsize=1 mm,1 mm,1 mm\nbins=1,1,1\n[scoring.mesh.Grid.Edep]\ntype=energyDeposit\nunit=MeV\n'
            fields=inspect('mesh-'+mode,f'[modules]\nscoring={mode}\n'+mesh)
            assert fields['/modules/objects/scoring/enabled']['resolved'] is True
            assert fields['/scoring/enabled']['resolved'] is False
            assert '/mesh/objects/Grid/shape' in fields
        assert 'conflicts' in inspect('mesh-off','[modules]\nscoring=off\n'+mesh,False)
        for token in ('', 'maybe', 'true'):
            assert 'off, auto or on' in inspect('bad-'+(token or 'empty'),f'[modules]\nscoring={token}\n',False)
        for name in ('geometry','source','physics','unknown'):
            assert 'unsupported optional module' in inspect('required-'+name,f'[modules]\n{name}=off\n',False)
        inactive=inspect('inactive','[modules]\nscoring=auto\nbiasing=auto\n[scoring]\nenabled=false\n[biasing]\nenabled=false\n')
        assert inactive['/modules/objects/scoring/enabled']['resolved'] is False
        assert inactive['/modules/objects/biasing/enabled']['resolved'] is False
    print('PASS: explicit optional module policies, distinct legacy/explicit auto, required core and invalid inputs')

if __name__=='__main__':
    main()

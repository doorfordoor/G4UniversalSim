"""New synthetic SDK-default fixtures only; not an archived CSV upgrader."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight'
TAIL = 'charge_eplus,dynamic_mass_MeV,electron_occupancy,magnetic_moment_MeV_per_T,polarization_x,polarization_y,polarization_z'
PURPOSES = {'scoring-numeric', 'j2-sources-physics', 'f1-input-resources', 'q1-results'}


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    assert condition, message


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_backend_identity(capabilities, identity, expected):
    """Compare actual two-binary identities, not directory names or SHA alone."""
    require(capabilities.get('schema') == 'G4UniversalSimCapabilities' and
            type(capabilities.get('version')) is int and capabilities['version'] == 1,
            'backend capabilities schema/version')
    require(capabilities.get('source_fingerprint') == expected, 'backend source mismatch')
    pairs = (('source_fingerprint', 'source_fingerprint'),
             ('geant4_version_number', 'geant4_version_number'),
             ('build_configuration', 'build_configuration'),
             ('compiler_id', 'compiler'), ('compiler_version', 'compiler_version'))
    for backend_key, helper_key in pairs:
        require(backend_key in capabilities and helper_key in identity, 'missing paired identity: '+backend_key)
        value = capabilities[backend_key]
        if backend_key == 'geant4_version_number':
            require(type(value) is int and value > 0 and type(identity[helper_key]) is int, 'actual SDK identity required')
        else:
            require(isinstance(value, str) and bool(value.strip()) and isinstance(identity[helper_key], str), 'nonempty build identity: '+backend_key)
        require(value == identity[helper_key], 'backend/helper mismatch: '+backend_key)
    require(capabilities['build_configuration'] in {'Debug', 'Release', 'RelWithDebInfo', 'MinSizeRel'}, 'formal build configuration required')


def synthetic_default_fixture(logical_rows: str, *, purpose: str, evidence: Path, backend: Path) -> str:
    """Accept newly composed logical rows, publish receipt, return verified v3 text.

    No file-path input, mass constants, state cache, or historical upgrade API.
    Caller freezes returned bytes BEFORE starting its backend/expected-input capture.
    """
    require(purpose in PURPOSES, 'explicit fixture purpose required')
    requested = list(csv.reader(io.StringIO(logical_rows)))
    require(requested and requested[0] == HEADER.split(','), 'canonical new logical request header')
    require(len(requested) > 1 and all(len(r) == 15 for r in requested[1:]), 'request rows must have 15 fields')
    for row in requested[1:]:
        require((row[4], row[5]) in {('proton', '2212'), ('gamma', '22')} and row[3] == '0', 'default proton/gamma primary only')
    # Keep native fixture receipts when a consumer uses TemporaryDirectory.
    evidence = (Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"]) / "phase-fixtures"
                if os.environ.get("G4USIM_TEST_EVIDENCE_DIR") else Path(evidence)).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    trial = Path(tempfile.mkdtemp(prefix=purpose+'-', dir=evidence))
    request = trial/'request.csv'
    request.write_bytes(('synthetic_sdk_default_state_fixture_request_v1\n'+logical_rows).encode('utf-8'))
    probe = Path(os.environ.get('G4USIM_PHASE_STATE_CHECK') or Path(backend).resolve().with_name('phaseSpaceStateCheck.exe' if os.name == 'nt' else 'phaseSpaceStateCheck')).resolve()
    receipt = {'kind': 'synthetic_sdk_default_state_fixture', 'no_transport': True,
               'status': 'preparing', 'purpose': purpose, 'request': str(request),
               'request_sha256': sha(request), 'backend': str(Path(backend).resolve()),
               'processes': []}
    try:
        require(probe.is_file(), 'candidate phaseSpaceStateCheck missing')
        from run_m0_tests import workspace_source_fingerprint
        expected = workspace_source_fingerprint()
        receipt.update(binary=str(probe), binary_sha256=sha(probe),
                       backend_sha256=sha(backend), expected_source_fingerprint=expected,
                       probe_sha256=sha(ROOT/'tools/phaseSpaceStateCheck.cc'),
                       wrapper_sha256=sha(__file__))
        for name, args in [('capabilities', ['--capabilities']), ('identity', ['--identity']), ('fixture', ['--synthetic-default-fixture', str(request), purpose, str(trial/'native')])]:
            require(sha(probe) == receipt['binary_sha256'], 'helper changed before invocation')
            require(sha(backend) == receipt['backend_sha256'], 'backend changed before invocation')
            executable = Path(backend).resolve() if name == 'capabilities' else probe
            process = {'argv': [str(executable), *args], 'cwd': str(trial), 'exit_code': None}
            receipt['processes'].append(process)
            with (trial/(name+'.stdout.log')).open('wb') as out, (trial/(name+'.stderr.log')).open('wb') as err:
                run = subprocess.run(process['argv'], cwd=trial, stdout=out, stderr=err, timeout=180)
            process['exit_code'] = run.returncode
            require(run.returncode == 0 and sha(probe) == receipt['binary_sha256'], name+' failed or binary drifted')
            require(sha(backend) == receipt['backend_sha256'], 'backend changed after invocation')
            if name == 'capabilities':
                capabilities = json.loads((trial/'capabilities.stdout.log').read_text(encoding='utf-8-sig'))
                require(capabilities.get('source_fingerprint') == expected, 'backend source mismatch')
                receipt['backend_capabilities'] = capabilities
            if name == 'identity':
                identity = json.loads((trial/'identity.stdout.log').read_text(encoding='utf-8-sig'))
                require(identity['source_fingerprint'] == expected and identity['probe_sha256'] == receipt['probe_sha256'], 'helper source/probe identity mismatch')
                require(identity['core_only'] is False and identity['geant4_version_number'] > 0, 'formal SDK helper required')
                verify_backend_identity(receipt['backend_capabilities'], identity, expected)
                receipt['identity'] = identity
        raw = json.loads((trial/'native/result.json').read_text(encoding='utf-8'))
        output = trial/'native/fixture.csv'
        require(raw['identity'] == receipt['identity'] and raw['purpose'] == purpose, 'raw receipt identity/purpose')
        require(raw['kind'] == receipt['kind'] and raw['no_transport'] is True, 'fixture scope receipt')
        require(raw['request_sha256'] == sha(request) == receipt['request_sha256'], 'request drift')
        require(raw['output_sha256'] == sha(output), 'output receipt SHA')
        text = output.read_bytes().decode('utf-8')
        actual = list(csv.reader(io.StringIO(text)))
        require(actual[0] == (HEADER+','+TAIL).split(','), 'canonical v3 header')
        require(len(actual) == len(requested) and raw['rows'] == len(requested)-1, 'row count/order')
        for i, (old, new) in enumerate(zip(requested[1:], actual[1:])):
            require(len(new) == 22, 'v3 row width')
            for j in range(15):
                if j == 4:
                    require(old[j] == new[j], f'particle row {i}')
                elif j in (0, 1, 2, 3, 5):
                    require(int(old[j]) == int(new[j]), f'ID row {i} column {j}')
                else:
                    a, b = float(old[j]), float(new[j])
                    require(math.isfinite(a) and math.isfinite(b) and a == b, f'logical field row {i} column {j}')
        require(sha(backend) == receipt['backend_sha256'], 'backend binary drift during fixture generation')
        receipt.update(status='verified', output=str(output), output_sha256=sha(output), logical_fields_verified=15)
        return text
    except BaseException as error:
        receipt.update(status='failed', error=str(error))
        raise
    finally:
        receipt['artifacts_sha256'] = {p.relative_to(trial).as_posix(): sha(p) for p in sorted(trial.rglob('*')) if p.is_file() and p.name != 'receipt.json'}
        (trial/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')

#!/usr/bin/env python3
"""Standalone Xerces exact-byte capture gate; run with a native Xerces C++ SDK.

This tests the same adapter used by GdmlIO, not an old Geant4 executable.
A complete newly-built Geant4 GDML regression remains a separate integration gate.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = (ROOT / "tools/gdmlInputCaptureCheck.cc").read_text(encoding="utf-8")

def main():
    compiler = os.environ.get('CXX') or shutil.which('g++')
    selected = os.environ.get('G4USIM_EXE')
    helper = Path(selected).resolve().with_name('gdmlInputCaptureCheck' + ('.exe' if os.name == 'nt' else '')) if selected else None
    assert (helper and helper.is_file()) or compiler, 'Built GDML capture helper or native Xerces C++ compiler required'
    with tempfile.TemporaryDirectory(prefix='g4usim-gdml-capture-') as temp:
        work = Path(temp)
        fixtures = {
            'replace.xml': b'original bytes\r\n',
            'entity.txt': b'accepted entity',
            'schema.xsd': b'<?xml version="1.0"?><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:element name="root" type="xs:string"/></xs:schema>',
            'main.xml': b'\xef\xbb\xbf<?xml version="1.0"?>\r\n<!DOCTYPE root [<!ENTITY external SYSTEM "entity.txt">]>\r\n<root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="schema.xsd">&external;</root>\r\n',
        }
        for name, content in fixtures.items():
            (work/name).write_bytes(content)
        source = work/'capture.cc'
        source.write_text(HARNESS,encoding='utf-8')
        executable = work/'capture'
        command = [compiler,'-std=c++17','-pthread','-DG4USIM_HAVE_GDML','-I'+str(ROOT/'include'),
                   str(source),str(ROOT/'src/Geometry/GdmlInputCapture.cc'),
                   str(ROOT/'src/Config/InputProvenance.cc'),'-lxerces-c','-o',str(executable)]
        if helper and helper.is_file():
            executable = helper
        else:
            compiled = subprocess.run(command,capture_output=True,text=True,timeout=120)
            assert compiled.returncode==0, compiled.stdout+compiled.stderr
        run = subprocess.run([str(executable),str(work)],capture_output=True,text=True,timeout=30)
        assert run.returncode==0, run.stdout+run.stderr
        assert 'PASS native capture' in run.stdout
        normalized_stdout = run.stdout.replace('\\', '/')
        for name, content in fixtures.items():
            assert f'/{name} {hashlib.sha256(content).hexdigest()}' in normalized_stdout, run.stdout
        assert (work/'written.txt').read_bytes()==b'keep'
        assert (work/'replace.xml').read_bytes()!=fixtures['replace.xml']
        assert 'http://example.test/schema.xsd '+hashlib.sha256(b'network bytes\r\n').hexdigest() in run.stdout
        assert 'UNKNOWN http://example.test/partial (stream did not reach EOF)' in run.stdout
        print(run.stdout)
    return 0
if __name__=='__main__':
    raise SystemExit(main())

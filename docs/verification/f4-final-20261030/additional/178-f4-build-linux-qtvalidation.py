import subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'out/collab/f4-qt-dependency-validation'
BUILD=Path('/home/u123/g4-f4-qt-validation-build114-20261030')
PREFIX=Path('/home/u123/g4env114')
configure=['cmake','-S',str(ROOT),'-B',str(BUILD),'-DCMAKE_BUILD_TYPE=Release',
    f'-DCMAKE_PREFIX_PATH={PREFIX}',f'-DGeant4_DIR={PREFIX}/lib/cmake/Geant4',
    f'-DEXPAT_INCLUDE_DIR={PREFIX}/include',f'-DEXPAT_LIBRARY={PREFIX}/lib/libexpat.so',
    f'-DZLIB_INCLUDE_DIR={PREFIX}/include',f'-DZLIB_LIBRARY={PREFIX}/lib/libz.so',
    f'-DFREETYPE_INCLUDE_DIRS={PREFIX}/include/freetype2',f'-DFREETYPE_LIBRARY={PREFIX}/lib/libfreetype.so',
    f'-DXercesC_INCLUDE_DIR={PREFIX}/include',f'-DXercesC_LIBRARY_RELEASE={PREFIX}/lib/libxerces-c.so']
commands=[configure,['cmake','--build',str(BUILD),'--target','G4UniversalSim','mergeHistograms','-j2']]
receipts=[]
for index,command in enumerate(commands):
    with (OUT/f'linux-build-{index}.log').open('wb') as log:
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    receipts.append({'command':command,'exit_code':result.returncode})
    (OUT/'linux-build-receipt.json').write_text(json.dumps(receipts,indent=2))
    if result.returncode:raise SystemExit(result.returncode)
print('Independent current-source Linux114 build complete:',BUILD,flush=True)

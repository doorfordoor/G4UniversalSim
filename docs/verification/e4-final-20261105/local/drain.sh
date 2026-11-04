set -e
export CONDA_PREFIX=/home/u123/g4env PATH=/home/u123/g4env/bin:$PATH LD_LIBRARY_PATH=/home/u123/g4gui-libs/usr/lib/x86_64-linux-gnu:/home/u123/g4env/lib QT_QPA_PLATFORM=offscreen
for f in "$CONDA_PREFIX"/etc/conda/activate.d/activate-geant4-data-*.sh; do source "$f"; done
cd /mnt/d/Geant4/G4UniversalSim
export E4_RUN_ROOT=/home/u123/g4-e4-verification-69003afd/run-drained
/home/u123/venvs/g4-j3-native-20261103/bin/python -B out/collab/e4-independent/rehearse.py out/collab/f2-independent-linux1132-build/G4UniversalSim >out/collab/e4-independent/linux-drained.log 2>&1
cp -a "$E4_RUN_ROOT" out/collab/e4-independent/linux-drained

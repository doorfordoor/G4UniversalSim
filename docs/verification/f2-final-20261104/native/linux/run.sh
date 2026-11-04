set -euo pipefail
export CONDA_PREFIX=/home/u123/g4env
export PATH="$CONDA_PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
set +u
for activation in "$CONDA_PREFIX"/etc/conda/activate.d/activate-geant4-data-*.sh; do source "$activation"; done
set -u
export GIT_DIR=/mnt/d/Geant4/G4UniversalSim/.git/worktrees/G4UniversalSim3
export GIT_WORK_TREE=/mnt/c/Users/123/.codex/worktrees/j3-final/G4UniversalSim
export G4USIM_REPO="$GIT_WORK_TREE"
export J3_R2_RUN_ROOT=/mnt/d/Geant4/G4UniversalSim/out/collab/f2-linux-native-independent/runs
bash /mnt/d/Geant4/G4UniversalSim/out/collab/f2-linux-native-independent/launch.sh

"""Create a portable Slurm config on the target installation, without changing PBS config."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from guard_mvp.io import Boundary

p = argparse.ArgumentParser()
p.add_argument('--node', required=True, help='Absolute path to Node.js on AAI')
a = p.parse_args()
b = Boundary(str(Path(__file__).resolve().parents[1]))
node = Path(a.node)
if not node.is_absolute() or not node.is_file():
    p.error('--node must identify the installed Node.js executable')
c = b.read('configs/experiment.yaml')
c.update(experiment_root=str(b.root), node=str(node), execution={'scheduler': 'slurm'})
target = b.path('configs/experiment.slurm.yaml')
if target.exists():
    p.error('Slurm config already exists; review it manually instead of overwriting')
b.json(target, c)
print(target)

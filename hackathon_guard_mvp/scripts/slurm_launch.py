"""Print AAI Slurm commands; never submits or guesses a partition/account."""
import shlex
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from guard_mvp.io import cli, entry


def options(p):
    p.add_argument('--stage', required=True, choices=('preflight', 'pilot', 'train', 'evaluate'))
    p.add_argument('--partition', required=True)
    p.add_argument('--account')
    p.add_argument('--time', default='01:00:00')
    p.add_argument('--mem', default='64G')
    p.add_argument('--afterok', type=int)
    p.add_argument('--condition', choices=('E0', 'E1', 'E2', 'E3'))


def main():
    args, b, c = cli('Print a Slurm submission command', options)
    if c.get('execution', {}).get('scheduler') != 'slurm':
        raise ValueError('use an explicit Slurm experiment configuration')
    if args.stage == 'evaluate' and not args.condition:
        raise ValueError('evaluation requires --condition')
    logs = b.path('runs/slurm')
    logs.mkdir(parents=True, exist_ok=True)
    command = ['sbatch', '--parsable', '--chdir', str(b.root), '--job-name', 'guard_' + args.stage,
               '--partition', args.partition, '--nodes=1', '--ntasks=1', '--cpus-per-task=4',
               '--gres=gpu:1', '--time', args.time, '--mem', args.mem,
               '--output', str(logs / (args.stage + '-%j.out')),
               '--error', str(logs / (args.stage + '-%j.err'))]
    if args.account:
        command += ['--account', args.account]
    if args.afterok is not None:
        if args.afterok <= 0:
            raise ValueError('invalid dependency job ID')
        command += ['--dependency', 'afterok:' + str(args.afterok)]
    command += [str(b.path('slurm/run.sh')), args.stage, str(b.path(Path(args.config).absolute()))]
    if args.condition:
        command.append(args.condition)
    print('cd ' + shlex.quote(str(b.root)))
    print(shlex.join(command))


if __name__ == '__main__':
    entry(main)

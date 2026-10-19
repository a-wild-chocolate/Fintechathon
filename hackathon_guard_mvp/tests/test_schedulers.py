import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from guard_mvp.workers import require_allocation


class SchedulerTests(unittest.TestCase):
    def check_gpu(self, config, env, name='NVIDIA A100', gib=40, bf16=True, count=1):
        cuda = SimpleNamespace(is_available=lambda: True, device_count=lambda: count,
                               is_bf16_supported=lambda: bf16,
                               get_device_properties=lambda _: SimpleNamespace(name=name, total_memory=gib * 2**30))
        torch = SimpleNamespace(cuda=cuda)
        with patch.dict(os.environ, env, clear=True), patch.dict(sys.modules, {'torch': torch}), \
                patch('guard_mvp.workers.platform.node', return_value='compute01'):
            return require_allocation(config)

    def test_slurm_allocated_bf16_gpu(self):
        self.check_gpu({'execution': {'scheduler': 'slurm'}},
                       {'SLURM_JOB_ID': '123', 'SLURM_JOB_NODELIST': 'node01', 'SLURM_JOB_GPUS': '0'})

    def test_slurm_rejects_notebook_without_gpu_allocation(self):
        for env in ({}, {'SLURM_JOB_ID': '123', 'SLURM_JOB_NODELIST': 'node01'}):
            with self.assertRaises(RuntimeError):
                self.check_gpu({'execution': {'scheduler': 'slurm'}}, env)

    def test_slurm_capacity_and_dtype_and_single_gpu(self):
        env = {'SLURM_JOB_ID': '123', 'SLURM_JOB_NODELIST': 'node01', 'SLURM_STEP_GPUS': '0'}
        for kwargs in ({'gib': 24}, {'bf16': False}, {'count': 2}):
            with self.assertRaises(RuntimeError):
                self.check_gpu({'execution': {'scheduler': 'slurm'}}, env, **kwargs)

    def test_pbs_still_requires_h200(self):
        env = {'PBS_JOBID': '123.gaas', 'PBS_NODEFILE': '/allocation/nodes'}
        with self.assertRaises(RuntimeError):
            self.check_gpu({}, env)
        self.check_gpu({}, env, name='NVIDIA H200', gib=140)

    def test_scheduler_mismatch_rejected(self):
        with self.assertRaises(RuntimeError):
            self.check_gpu({}, {'SLURM_JOB_ID': '123', 'SLURM_JOB_NODELIST': 'node01', 'SLURM_JOB_GPUS': '0'})

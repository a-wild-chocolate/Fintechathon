"""CPU-safe import: no workers, evaluator, torch, or external services imported."""
import sys
sys.dont_write_bytecode = True
__version__ = "0.1.0"

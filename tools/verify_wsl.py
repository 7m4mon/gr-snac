"""Print installed versions and perform a minimal CPU tensor operation."""
import sys
import importlib.metadata
import numpy as np
import torch
from gnuradio import gr, snac
from snac import SNAC

print("Python:", sys.version.split()[0])
print("GNU Radio:", gr.version())
print("PyTorch:", torch.__version__)
print("SNAC:", importlib.metadata.version("snac"))
print("NumPy:", np.__version__)
print("CUDA available:", torch.cuda.is_available())
print("CPU tensor:", (torch.arange(4) ** 2).tolist())
print("OOT:", snac.__file__)

"""FaaSr step 6: pyadm1 (function name run_pyadm1).

Run the PyADM1 anaerobic-digestion simulation on the cleaned influent and the
initial-state file, producing dynamic_out.csv.

The provided PyADM1.py (shipped in the same repo folder) has its driver code
guarded by `if __name__ == "__main__":`, so importing it is side-effect free.
When executed as "__main__" it reads "digester_influent.csv" and
"digester_initial.csv" from the current working directory and writes
"dynamic_out.csv" there. We download the two cleaned inputs under exactly those
local names and then execute the script via runpy.

NB: the function is deliberately NOT named "pyadm1" so its module file cannot
collide (case-insensitively) with PyADM1.py; the workflow action id is still
"pyadm1".
"""

try:
    from FaaSr_py.client.py_client_stubs import faasr_get_file, faasr_put_file, faasr_log
except Exception:  # pragma: no cover - stubs injected into globals at runtime
    pass

import importlib.util
import os
import runpy
import sys

import matplotlib
matplotlib.use("Agg")  # headless backend; PyADM1.py imports matplotlib.pyplot


def _find_pyadm1():
    """Locate PyADM1.py, which ships in the same repo folder (on sys.path)."""
    spec = importlib.util.find_spec("PyADM1")
    if spec is not None and spec.origin:
        return spec.origin
    for d in sys.path:
        candidate = os.path.join(d or ".", "PyADM1.py")
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError("PyADM1.py not found on sys.path")


def run_pyadm1(folder, influent_file="digester_influent.csv",
               initial_file="digester_initial.csv",
               output_file="dynamic_out.csv"):
    # PyADM1.py hard-codes these local filenames, so download to matching names.
    faasr_log(f"run_pyadm1: downloading {folder}/{influent_file} and {folder}/{initial_file}")
    faasr_get_file(remote_folder=folder, remote_file=influent_file,
                   local_folder=".", local_file="digester_influent.csv")
    faasr_get_file(remote_folder=folder, remote_file=initial_file,
                   local_folder=".", local_file="digester_initial.csv")

    script_path = _find_pyadm1()
    faasr_log(f"run_pyadm1: executing PyADM1 simulation from {script_path}")
    # run_path executes the script's guarded driver (run_name='__main__') in a
    # fresh namespace, reading the two CSVs from the CWD and writing
    # dynamic_out.csv to the CWD.
    runpy.run_path(script_path, run_name="__main__")

    if not os.path.isfile("dynamic_out.csv"):
        raise RuntimeError("run_pyadm1: simulation did not produce dynamic_out.csv")

    faasr_put_file(local_folder=".", local_file="dynamic_out.csv",
                   remote_folder=folder, remote_file=output_file)
    faasr_log(f"run_pyadm1: simulation complete; wrote {folder}/{output_file}")

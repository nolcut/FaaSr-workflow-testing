import os
import sys
import subprocess


def run_pyadm1(folder="PyADM1-orig",
               influent_file="digester_influent.csv",
               initial_file="digester_initial.csv",
               script_file="PyADM1.py",
               output_file="dynamic_out.csv"):
    """Step 6 - run the PyADM1 simulation on the cleaned influent + initial state.

    PyADM1.py is a standalone script that reads 'digester_influent.csv' and
    'digester_initial.csv' from the working directory and writes 'dynamic_out.csv'.
    We download the cleaned inputs under exactly those names, download the
    simulation script, then execute it in an isolated subprocess (so its
    top-level code runs cleanly), and upload the resulting dynamic_out.csv.
    """
    # PyADM1.py hard-codes these local filenames.
    faasr_get_file(remote_folder=folder, remote_file=influent_file,
                   local_file="digester_influent.csv")
    faasr_get_file(remote_folder=folder, remote_file=initial_file,
                   local_file="digester_initial.csv")
    faasr_get_file(remote_folder=folder, remote_file=script_file,
                   local_file="PyADM1.py")

    faasr_log("run_pyadm1: launching PyADM1 simulation")
    proc = subprocess.run([sys.executable, "PyADM1.py"],
                          capture_output=True, text=True)
    if proc.stdout:
        faasr_log("run_pyadm1 stdout: " + proc.stdout[-2000:])
    if proc.returncode != 0:
        faasr_log("run_pyadm1 stderr: " + (proc.stderr or "")[-4000:])
        raise RuntimeError(f"PyADM1.py failed with exit code {proc.returncode}")

    if not os.path.exists("dynamic_out.csv"):
        raise FileNotFoundError("PyADM1.py did not produce dynamic_out.csv")

    faasr_put_file(local_file="dynamic_out.csv", remote_folder=folder, remote_file=output_file)
    faasr_log(f"run_pyadm1: simulation complete; wrote {folder}/{output_file}")

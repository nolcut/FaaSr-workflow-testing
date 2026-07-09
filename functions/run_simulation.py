import os
import runpy


def _locate_pyadm1():
    """Find PyADM1.py within the cloned function repository."""
    candidates = [
        "PyADM1.py",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "PyADM1.py"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    # Fall back to walking the tree from the current working directory.
    for root, _dirs, files in os.walk("."):
        if "PyADM1.py" in files:
            return os.path.abspath(os.path.join(root, "PyADM1.py"))
    raise FileNotFoundError("PyADM1.py could not be located in the function repository")


def run_simulation(folder, influent_file, initial_file, output_file):
    """
    FaaSr function: run the PyADM1 anaerobic digestion simulation.

    Downloads the two validated input CSVs from S3 into the working directory
    under the exact filenames PyADM1.py expects ("digester_influent.csv" and
    "digester_initial.csv"), executes the PyADM1 script (which writes
    "dynamic_out.csv"), and uploads the result back to S3 as `output_file`.
    """

    # --- Download inputs under the names PyADM1.py reads ---------------------
    faasr_get_file(remote_folder=folder, remote_file=influent_file,
                   local_folder=".", local_file="digester_influent.csv")
    faasr_get_file(remote_folder=folder, remote_file=initial_file,
                   local_folder=".", local_file="digester_initial.csv")

    faasr_log("Inputs downloaded. Starting PyADM1 dynamic simulation ...")

    # --- Run PyADM1 ----------------------------------------------------------
    # PyADM1.py is a top-level script: importing/executing it reads the CSVs
    # from the current directory, runs the full dynamic simulation, and writes
    # "dynamic_out.csv". runpy executes it in a fresh namespace.
    script_path = _locate_pyadm1()
    runpy.run_path(script_path, run_name="__main__")

    if not os.path.isfile("dynamic_out.csv"):
        raise FileNotFoundError("PyADM1 did not produce dynamic_out.csv")

    faasr_log("PyADM1 simulation finished; dynamic_out.csv produced.")

    # --- Upload result -------------------------------------------------------
    faasr_put_file(local_folder=".", local_file="dynamic_out.csv",
                   remote_folder=folder, remote_file=output_file)

    faasr_log(f"Simulation output uploaded to {folder}/{output_file}.")
    return True

import os
import sys
import subprocess


def run_pyadm1(validated_folder="pyadm1-validated",
               output_folder="pyadm1-outputs",
               influent_file="digester_influent.csv",
               initial_file="digester_initial.csv",
               output_file="dynamic_out.csv"):
    """
    FaaSr stage 2 of 3.

    Downloads the validated PyADM1 input CSVs from S3 into the working
    directory (PyADM1.py reads them by their fixed local names), executes the
    user-provided PyADM1.py anaerobic-digestion model, and uploads the
    resulting dynamic simulation output (dynamic_out.csv) back to S3 for the
    visualization stage.
    """

    # PyADM1.py reads exactly these two local filenames from the cwd.
    faasr_get_file(remote_folder=validated_folder, remote_file=influent_file,
                   local_folder=".", local_file="digester_influent.csv")
    faasr_get_file(remote_folder=validated_folder, remote_file=initial_file,
                   local_folder=".", local_file="digester_initial.csv")
    faasr_log("run_pyadm1: downloaded validated inputs; starting PyADM1 "
              "simulation.")

    # Locate PyADM1.py next to this function file (both are cloned from the
    # FunctionGitRepo into the working directory).
    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, "PyADM1.py")
    if not os.path.exists(script):
        script = "PyADM1.py"  # fall back to cwd

    # Run the model as a subprocess so its module-level script body executes
    # unmodified. It writes dynamic_out.csv into the cwd.
    proc = subprocess.run([sys.executable, script],
                          capture_output=True, text=True)
    if proc.stdout:
        faasr_log("run_pyadm1 stdout: " + proc.stdout[-2000:])
    if proc.returncode != 0:
        faasr_log("run_pyadm1 stderr: " + proc.stderr[-4000:])
        raise RuntimeError(
            f"PyADM1.py failed with exit code {proc.returncode}")

    if not os.path.exists(output_file):
        raise FileNotFoundError(
            f"PyADM1.py finished but did not produce {output_file}")

    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=output_folder, remote_file=output_file)
    faasr_log(f"run_pyadm1: simulation complete; {output_file} uploaded to "
              f"prefix '{output_folder}'.")

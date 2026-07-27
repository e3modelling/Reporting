#!/usr/bin/env python3
# ============================================================================
# daily_report.py
#
# Generates the "Daily Run Report" README for the e3modelling/Reporting repo
# and pushes it. Called at the end of daily_run.bat.
#
# Rewrite of the repo's DR.py / DR_server.py with three changes:
#   1. Success is decided by plot.pdf AND reporting.mif both existing.
#      (The original checked for "blabla.gdx", a placeholder that never
#      exists, so every run was always marked "failed".)
#   2. A header line above the table reports the mrprom / postprom install +
#      verification status for the whole run.
#   3. Paths, run count and the install-status source are taken from the
#      environment / CLI, so the same file works on every machine instead of
#      hard-coding one user's Desktop path.
#
# All configuration comes from environment variables (daily_run.bat sets
# them) with CLI overrides:
#
#   RUNS_DIR        directory containing the per-scenario run folders
#   REPORT_REPO     local checkout of e3modelling/Reporting
#   INSTALL_STATUS  "ok" | "failed" | free text  (mrprom/postprom install)
#   N_RUNS          how many of the most recent folders to report (default 4)
#   NO_PUSH         if set to 1, write README but do not commit/push
#
#   --runs-dir / --repo / --install-status / --n / --no-push  override each.
# ============================================================================

import argparse
import os
import subprocess
import sys
from datetime import datetime


def parse_args():
    p = argparse.ArgumentParser(description="Generate and push the daily run report.")
    p.add_argument("--runs-dir",       default=os.environ.get("RUNS_DIR", ""))
    p.add_argument("--repo",           default=os.environ.get("REPORT_REPO", ""))
    p.add_argument("--install-status", default=os.environ.get("INSTALL_STATUS", "unknown"))
    p.add_argument("--n",   type=int,  default=int(os.environ.get("N_RUNS", "4")))
    p.add_argument("--no-push", action="store_true",
                   default=os.environ.get("NO_PUSH", "") == "1")
    return p.parse_args()


def recent_folders(runs_dir, n):
    if not os.path.isdir(runs_dir):
        return []
    folders = [f.path for f in os.scandir(runs_dir) if f.is_dir()]
    folders.sort(key=lambda x: os.path.getctime(x), reverse=True)
    return folders[:n]


def exists_in(folder, name):
    return os.path.exists(os.path.join(folder, name))


def run_time_minutes(folder):
    created = os.path.getctime(folder)
    modified = os.path.getmtime(folder)
    return round((modified - created) / 60, 2)


def calibration_status(folder):
    """Successful / Failed / N/A, from the GAMS calibration listing."""
    if not exists_in(folder, "mainCalib.lst"):
        return "N/A"                      # not a calibration run
    log = os.path.join(folder, "fullCalib.log")
    if not os.path.exists(log):
        return "Failed"
    try:
        with open(log, "r", encoding="utf-8", errors="ignore") as f:
            tail = f.readlines()[-50:]
        for line in tail:
            if "*** Status: Normal completion" in line:
                return "Successful"
        return "Failed"
    except OSError as e:
        print(f"Could not read {log}: {e}", file=sys.stderr)
        return "Failed"


def is_calibration_folder(name):
    # Calibration runs are the NPi task-3 run (rebuilds data) or SCEN_ runs.
    return name.startswith("DAILY_NPi_") or name.startswith("SCEN_")


def scenario_rows(folders):
    """Build one row per folder. Success = plot.pdf AND reporting.mif."""
    rows = []
    any_calib_failed = False

    for folder in folders:
        name = os.path.basename(folder)

        plot_pdf = exists_in(folder, "plot.pdf")
        reporting_mif = exists_in(folder, "reporting.mif")
        # Agreed success criterion: both artifacts present.
        status = "successful" if (plot_pdf and reporting_mif) else "failed"

        if is_calibration_folder(name):
            calib = calibration_status(folder)
            if calib == "Failed":
                any_calib_failed = True
        else:
            calib = "-"

        rows.append({
            "name": name,
            "status": status,
            "run_time": run_time_minutes(folder),
            "calibration": calib,
            "plot_pdf": "Yes" if plot_pdf else "No",
            "reporting_mif": "Yes" if reporting_mif else "No",
        })
    return rows, any_calib_failed


def install_header(install_status):
    s = (install_status or "unknown").strip()
    low = s.lower()
    if low == "ok":
        return "**Environment:** mrprom + postprom installed and verified \u2705"
    if low in ("failed", "fail", "error"):
        return "**Environment:** mrprom / postprom install or verification FAILED \u274c"
    if low == "unknown":
        return "**Environment:** mrprom / postprom install status unknown \u2753"
    # Any other value: show it verbatim so a custom message survives.
    return f"**Environment:** {s}"


def build_markdown(rows, install_status, calib_failed):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if calib_failed:
        ts += " \u2014 CALIBRATION FAILED"

    out = [
        "# Daily Run Report",
        f"Generated on {ts}",
        "",
        install_header(install_status),
        "",
        "| Folder Name | Status | Run Time (min) | Calibration | Plot.pdf | Reporting.mif |",
        "|-------------|--------|----------------|-------------|----------|---------------|",
    ]
    for r in rows:
        out.append(
            f"| {r['name']} | {r['status']} | {r['run_time']} | "
            f"{r['calibration']} | {r['plot_pdf']} | {r['reporting_mif']} |"
        )
    if not rows:
        out.append("| _(no run folders found)_ | - | - | - | - | - |")
    return "\n".join(out) + "\n"


def write_readme(repo_path, content):
    path = os.path.join(repo_path, "README.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def commit_and_push(repo_path):
    log_file = os.path.join(repo_path, "git_log.txt")

    def log(msg):
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"{datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')} {msg}\n")

    def git(*a):
        return subprocess.run(["git", *a], cwd=repo_path,
                              capture_output=True, text=True, check=True)

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        log("Error: not a git repository.")
        print(f"ERROR: {repo_path} is not a git repository.", file=sys.stderr)
        return False
    try:
        git("add", "README.md")
        status = git("status", "--porcelain")
        if not status.stdout.strip():
            log("Nothing to commit.")
            print("README unchanged - nothing to push.")
            return True
        git("commit", "-m", "Update daily run report")
        git("push")
        log("Successfully committed and pushed README.md.")
        print("Report committed and pushed.")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Git error: {e}\nstdout: {e.stdout}\nstderr: {e.stderr}")
        print(f"Git error: {e.stderr or e}", file=sys.stderr)
        return False


def main():
    args = parse_args()

    if not args.runs_dir:
        print("ERROR: runs directory not set (RUNS_DIR or --runs-dir).", file=sys.stderr)
        sys.exit(2)
    if not args.repo:
        print("ERROR: report repo not set (REPORT_REPO or --repo).", file=sys.stderr)
        sys.exit(2)

    folders = recent_folders(args.runs_dir, args.n)
    if not folders:
        print(f"WARNING: no run folders under {args.runs_dir}", file=sys.stderr)

    rows, calib_failed = scenario_rows(folders)
    md = build_markdown(rows, args.install_status, calib_failed)

    write_readme(args.repo, md)
    print(f"README written to {os.path.join(args.repo, 'README.md')}")

    pushed = True
    if args.no_push:
        print("--no-push set: skipping commit/push.")
    else:
        pushed = commit_and_push(args.repo)

    # Non-zero exit if calibration failed or the push failed, so the scheduler
    # surfaces it. A plain "some scenarios failed" is reported, not fatal --
    # the report itself is the deliverable and it succeeded.
    if calib_failed:
        print("Calibration failed - see report.", file=sys.stderr)
        sys.exit(1)
    if not pushed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

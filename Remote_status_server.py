import os
import subprocess
import sys
from datetime import datetime

# -------------------------------------------------
# Configuration
# -------------------------------------------------

# Remote health log (produced by PowerShell script)
remote_health_log = r"C:\Models\remote-health.log"

# Repo where the status file will be committed
repo_path = r"C:\Models\Reporting"

# Status file inside the repo
status_file_name = "remote_server_status.txt"

# Staleness threshold
health_stale_minutes = 90


# -------------------------------------------------
# Remote health check (LOG PARSING)
# -------------------------------------------------
def check_remote_health():
    if not os.path.exists(remote_health_log):
        return False, "Health log missing or server unreachable"

    try:
        last_write = datetime.fromtimestamp(os.path.getmtime(remote_health_log))
    except Exception as e:
        return False, f"Cannot stat health log ({e})"

    age_minutes = (datetime.now() - last_write).total_seconds() / 60
    if age_minutes > health_stale_minutes:
        return False, f"Health log stale ({round(age_minutes,1)} minutes)"

    try:
        with open(remote_health_log, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        return False, f"Cannot read health log ({e})"

    for line in reversed(lines):
        if line.startswith("STATUS:"):
            if line.strip() == "STATUS: OK":
                return True, "Remote server accessible"
            else:
                return False, line.strip().replace("STATUS:", "").strip()

    return False, "No STATUS line found in health log"


# -------------------------------------------------
# Write plain-text status file
# -------------------------------------------------
def write_status_file(ok, message):
    status_path = os.path.join(repo_path, status_file_name)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_text = "OK" if ok else "FAILURE"

    content = [
        f"Timestamp : {timestamp}",
        f"Status    : {status_text}",
        f"Message   : {message}",
    ]

    with open(status_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content) + "\n")

    return status_path


# -------------------------------------------------
# Git commit & push
# -------------------------------------------------
def commit_and_push(file_path):
    try:
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            print("ERROR: Target directory is not a git repository")
            return

        subprocess.run(
            ["git", "add", os.path.basename(file_path)],
            cwd=repo_path,
            check=True
        )

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )

        if not status.stdout.strip():
            print("No changes to commit.")
            return

        subprocess.run(
            ["git", "commit", "-m", "Update remote server accessibility status"],
            cwd=repo_path,
            check=True
        )

        subprocess.run(
            ["git", "push"],
            cwd=repo_path,
            check=True
        )

        print("Status file committed and pushed.")

    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")


def main():
    ok, message = check_remote_health()

    # Always write status file (even on failure)
    status_path = write_status_file(ok, message)

    # Commit result to repo
    commit_and_push(status_path)

    # Exit code for schedulers / CI
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

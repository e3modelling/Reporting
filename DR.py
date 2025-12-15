import os
import subprocess
import sys
from datetime import datetime

# Define the directory path where the folders are located
directory_path = r"C:\Users\Plessias\Desktop\Scheduled_OPEN-PROM\OPEN-PROM\runs"
repo_path = r"C:\Users\Plessias\Reporting"  # Path to the local Git repo

def get_last_4_folders(directory_path):
    folders = [f.path for f in os.scandir(directory_path) if f.is_dir()]
    folders.sort(key=lambda x: os.path.getctime(x), reverse=True)
    return folders[:4]

def check_file_in_folder(folder_path):
    return os.path.exists(os.path.join(folder_path, "blabla.gdx"))

def check_plot_pdf(folder_path):
    """Check if plot.pdf exists in the folder."""
    return "Yes" if os.path.exists(os.path.join(folder_path, "plot.pdf")) else "No"

def check_reporting_mif(folder_path):
    """Check if reporting.mif exists in the folder."""
    return "Yes" if os.path.exists(os.path.join(folder_path, "reporting.mif")) else "No"

def check_calibration_status(folder_path):
    """Check if calibration was successful for DAILY_NPi_ folders."""
    main_calib_path = os.path.join(folder_path, "mainCalib.lst")
    
    if not os.path.exists(main_calib_path):
        return "N/A"  # Not a calibration run
    
    full_calib_path = os.path.join(folder_path, "fullCalib.log")
    
    if not os.path.exists(full_calib_path):
        return "Failed"  # mainCalib.lst exists but fullCalib.log doesn't
    
    try:
        with open(full_calib_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        # Check the last 20 lines for the completion status
        last_lines = lines[-20:] if len(lines) > 20 else lines
        
        for line in last_lines:
            line_stripped = line.strip()
            if "*** Status: Normal completion" in line_stripped:
                return "Successful"
                
        return "Failed"
        
    except Exception as e:
        print(f"Error reading calibration file {full_calib_path}: {e}")
        return "Failed"

def is_daily_npi_folder(folder_name):
    """Check if the folder name starts with DAILY_NPi_."""
    return folder_name.startswith("DAILY_NPi_")

def calculate_run_time(folder_path):
    creation_time = os.path.getctime(folder_path)
    last_mod_time = os.path.getmtime(folder_path)
    run_time_minutes = (last_mod_time - creation_time) / 60
    return round(run_time_minutes, 2)

def generate_markdown(folders_info):
    lines = [
        "# Daily Run Report",
        f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Folder Name | Status     | Run Time (min) | Calibration | Plot.pdf | Reporting.mif |",
        "|-------------|------------|----------------|-------------|----------|---------------|"
    ]
    for folder_name, status, run_time, calibration, plot_pdf, reporting_mif in folders_info:
        lines.append(f"| {folder_name} | {status} | {run_time} | {calibration} | {plot_pdf} | {reporting_mif} |")
    return "\n".join(lines)

def write_readme(content):
    readme_path = os.path.join(repo_path, "README.md")
    with open(readme_path, "w") as f:
        f.write(content)

def commit_and_push():
    log_file = os.path.join(repo_path, "git_log.txt")

    def log(message):
        with open(log_file, "a") as logf:
            timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
            logf.write(f"{timestamp} {message}\n")

    try:
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            log("Error: Not a git repository.")
            return

        log("Staging README.md...")
        result=subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
        log(f"STDOUT: {result.stdout}")
        log(f"STDERR: {result.stderr}")
        
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_path, capture_output=True, text=True)
        if status.stdout.strip() == "":
            log("Nothing to commit.")
            return

        log("Committing changes...")
        result=subprocess.run(["git", "commit", "-m", "Update daily run report"], cwd=repo_path, check=True)
        log(f"STDOUT: {result.stdout}")
        log(f"STDERR: {result.stderr}")

        log("Pushing to origin...")
        result=subprocess.run(["git", "push"], cwd=repo_path, check=True)
        log(f"STDOUT: {result.stdout}")
        log(f"STDERR: {result.stderr}")

        log("Successfully committed and pushed README.md.")
    except subprocess.CalledProcessError as e:
        log(f"Git error: {e}")

def main():
    folders = get_last_4_folders(directory_path)
    folders_info = []
    calibration_failed = False

    for i, folder in enumerate(folders):
        folder_name = os.path.basename(folder)
        status = "successful" if check_file_in_folder(folder) else "failed"
        run_time = calculate_run_time(folder)
        
        # Check calibration status for any DAILY_NPi_ folder
        if is_daily_npi_folder(folder_name):
            calibration_status = check_calibration_status(folder)
            if calibration_status == "Failed":
                calibration_failed = True
                print(f"CRITICAL ERROR: Calibration failed for {folder_name}. Terminating process.")
        else:
            calibration_status = "-"
        
        # Check for plot.pdf in all folders
        plot_pdf_status = check_plot_pdf(folder)
        
        # Check for reporting.mif in all folders
        reporting_mif_status = check_reporting_mif(folder)
        
        folders_info.append((folder_name, status, run_time, calibration_status, plot_pdf_status, reporting_mif_status))

    # If calibration failed, terminate the process before generating report
    if calibration_failed:
        print("Process terminated due to calibration failure. Regular runs will not proceed.")
        sys.exit(1)

    markdown_content = generate_markdown(folders_info)
    write_readme(markdown_content)
    commit_and_push()

if __name__ == "__main__":
    main()

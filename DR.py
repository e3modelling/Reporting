import os
import subprocess
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
        "| Folder Name | Status     | Run Time (min) |",
        "|-------------|------------|----------------|"
    ]
    for folder_name, status, run_time in folders_info:
        lines.append(f"| {folder_name} | {status} | {run_time} |")
    return "\n".join(lines)

def write_readme(content):
    readme_path = os.path.join(repo_path, "README.md")
    with open(readme_path, "w") as f:
        f.write(content)

def commit_and_push():
    try:
        subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Update daily run report"], cwd=repo_path, check=True)
        subprocess.run(["git", "push"], cwd=repo_path, check=True)
        print("README.md committed and pushed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")

def main():
    folders = get_last_4_folders(directory_path)
    folders_info = []

    for folder in folders:
        folder_name = os.path.basename(folder)
        status = "successful" if check_file_in_folder(folder) else "failed"
        run_time = calculate_run_time(folder)
        folders_info.append((folder_name, status, run_time))

    markdown_content = generate_markdown(folders_info)
    write_readme(markdown_content)
    commit_and_push()

if __name__ == "__main__":
    main()

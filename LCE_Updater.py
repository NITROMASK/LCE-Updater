import os
import sys
import requests
import zipfile
import subprocess
import shutil
import argparse
from tqdm import tqdm

#Info
#Main build is the most stable and its recommended to use it!!


#This is the config where you can edit what platform you want etc.

OWNER = "smartcmd"
REPO = "MinecraftConsoles"
WORK_DIR = "tmp_update"
UPDATE_FILE_ZIP = "Update"
BUILD_CONFIG = "Release"
#I Recommend not to change the platform because i didn't test it
#Just Stay with windows compiling
PLATFORM = "Windows64"
LOCAL_VERSION_FILE = "local_version.txt"
BUILD_LOG_FILE = "build.log"
#Debug mode just gives more info for debugging errors
LCE_UPDATER_DEBUG_MODE = False

'''FOLDERS_TO_SYNC = [
    "Common",
    "Durango",
    "Music",
    "Redist64",
    "Windows64",
    "Windows64_Media"
]
not needed anymore.
'''


#Error message code

def safe_exit(message):
    print(f"\nError: {message}")
    sys.exit(1)

#Clears screen im planing to add linux at some point so it is multi os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# This is for detecting MSBUILD if it isnt installed it quits

def find_msbuild():
    vswhere = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    if not os.path.exists(vswhere):
        safe_exit("vswhere not found. Install Visual Studio with MSBuild.")

    try:
        output = subprocess.check_output([
            vswhere,
            "-latest",
            "-products", "*",
            "-requires", "Microsoft.Component.MSBuild",
            "-find", "MSBuild\\**\\Bin\\MSBuild.exe"
        ]).decode().strip()

        if not output:
            safe_exit("MSBuild not found.")

        return output

    except subprocess.CalledProcessError:
        safe_exit("Failed to locate MSBuild.")


# Github Part
#for some reason if it cant fetch it it crashes so ill just leave it alone

def get_branches():
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/branches"
    r = requests.get(url)
    if LCE_UPDATER_DEBUG_MODE == True:
        print("Status code:", r.status_code)
        print("Response:", r.text)
    
    if r.status_code != 200:
        safe_exit("Failed to fetch branches from GitHub API.")
    return r.json()


def select_branch_menu():
    branches = get_branches()
    print("\nAvailable Branches:\n")
    for i, b in enumerate(branches, 1):
        print(f"{i}. {b['name']}")

    while True:
        choice = input("\nSelect branch (default 1): ").strip()
        if choice == "":
            return branches[0]
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(branches):
                return branches[index - 1]
        print("Invalid selection.")


# This one creates a version hash so when LCE is up to date it asks if you wanna update.
# IN TETSTING


def is_latest(remote_sha):
    if not os.path.exists(LOCAL_VERSION_FILE):
        return False
    with open(LOCAL_VERSION_FILE, "r") as f:
        return f.read().strip() == remote_sha

def save_version(sha):
    with open(LOCAL_VERSION_FILE, "w") as f:
        f.write(sha)


# This part is for downloading the Repo zip file

def download(url: str, fname: str, chunk_size=1024):
    resp = requests.get(url, stream=True)
    if resp.status_code != 200:
        safe_exit("Download failed.")

    total = int(resp.headers.get('content-length', 0))
    with open(fname, 'wb') as file, tqdm(
        desc=os.path.basename(fname),
        total=total,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024
    ) as bar:
        for data in resp.iter_content(chunk_size=chunk_size):
            size = file.write(data)
            bar.update(size)


def download_branch(branch_name):
    url = f"https://github.com/{OWNER}/{REPO}/archive/refs/heads/{branch_name}.zip"
    zip_path = os.path.join(UPDATE_FILE_ZIP, "repo.zip")
    
    print(f"\nDownloading branch: {branch_name}\n")
    download(url, zip_path)
    return zip_path


# Extract the folder and the progress bar

def extract_zip(zip_path):
    
    clear_screen()
    
    print("\nExtracting...\n")
    extract_to = WORK_DIR  # extract inside tmp folder

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        members = zip_ref.infolist()
        with tqdm(total=len(members), desc="Extracting", unit="file") as bar:
            for member in members:
                zip_ref.extract(member, extract_to)
                bar.update(1)

    # Return the folder that was just extracted
    for item in os.listdir(extract_to):
        path = os.path.join(extract_to, item)
        if os.path.isdir(path) and item.startswith(f"{REPO}-"):
            return path

    safe_exit("Extraction failed.")


# Find Solution

def find_solution(folder):
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".sln"):
                return os.path.join(root, file)
    safe_exit("Solution file not found.")


#Real time Build Log

def build_solution(msbuild, solution):
    clear_screen()
    
    print(r"Building...")
    print(r"This can take a while")
    print(r"Please be Patient!")
    cmd = [
        msbuild,
        solution,
        f"/p:Configuration={BUILD_CONFIG}",
        f"/p:Platform={PLATFORM}",
        "/m",
        "/fl",
        f"/flp:logfile={BUILD_LOG_FILE};verbosity=diagnostic"
    ]
    process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    process.wait()
    if process.returncode != 0:
        print("Build failed. See build.log for details.")
        input("Press Enter to continue...")
        sys.exit(1)
    print("Build completed successfully.\n")


#edited sync so it only copies


def sync_to_script_dir(source_root, branch_name):
    cwd = os.getcwd()  # where the script was run
    release_path = os.path.join(source_root, "x64", "Release")

    if not os.path.exists(release_path):
        print(f"Warning: Release folder not found at {release_path}")
        return

    for item in os.listdir(release_path):
        src = os.path.join(release_path, item)
        dest = os.path.join(cwd, item)

        if os.path.isfile(src):
            shutil.copy2(src, dest)
            print(f"Copied file: {dest}")
        elif os.path.isdir(src):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            print(f"Copied folder: {dest}")




    #Main

def main():
    print(r"""  _    ___ ___   _   _ ___ ___   _ _____ ___ ___ 
 | |  / __| __| | | | | _ \   \ /_\_   _| __| _ \
 | |_| (__| _|  | |_| |  _/ |) / _ \| | | _||   /
 |____\___|___|  \___/|_| |___/_/ \_\_| |___|_|_\
                                                 """)
    print("         Legacy Console Edition Updater")
    print("                 Made By Maskie")
    print("v0.2")
    
    if LCE_UPDATER_DEBUG_MODE == True:
        print("LCE UPDATER IS IN DEBUG MODE IT WILL SHOW MORE INFO...")
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", help="Use manually downloaded zip file")
    args = parser.parse_args()

    # ensure temp folder exists
    if os.path.exists(WORK_DIR):
        shutil.rmtree(WORK_DIR)
    os.makedirs(WORK_DIR, exist_ok=True)
    
    os.makedirs(UPDATE_FILE_ZIP, exist_ok=True)

    #Manual Mode if you have a zip
    if args.zip:
        zip_path = args.zip

        if not os.path.exists(zip_path):
            safe_exit("Provided zip file does not exist.")

        print(f"\nUsing manual zip: {zip_path}\n")

        source_folder = extract_zip(zip_path)
        solution = find_solution(source_folder)

        msbuild = find_msbuild()
        build_solution(msbuild, solution)


        shutil.rmtree(WORK_DIR)

        print("\nBuild completed using manual zip.")
        return

    #Normal Mode

    branch = select_branch_menu()
    branch_name = branch["name"]
    remote_sha = branch["commit"]["sha"]
    
    clear_screen()
    
    print(f"\nSelected branch: {branch_name}")

    # Read installed commit
    if os.path.exists(LOCAL_VERSION_FILE):
        with open(LOCAL_VERSION_FILE, "r") as f:
            installed_commit = f.read().strip()
    else:
        installed_commit = None

    print(f"Installed Commit: {installed_commit or 'None'}")
    print(f"Latest Commit   : {remote_sha}")

    # Determine prompt text based on update status
    if installed_commit == remote_sha:
        print("\nAlready up to date.")
        prompt_text = "Do you want to rebuild anyway? (y/n): "
    else:
        print("\nNew update available!")
        prompt_text = "Do you want to update now? (y/n): "

    # Ask the user
    while True:
        choice = input(prompt_text).strip().lower()
        if choice in ("y", "yes"):
            if installed_commit == remote_sha:
                print("\nRebuilding current version from existing zip...\n")
                zip_path = os.path.join(UPDATE_FILE_ZIP, "repo.zip")
                if not os.path.exists(zip_path):
                    safe_exit("Existing zip not found! Cannot rebuild.")
            else:
                print("\nUpdating to latest version...\n")
                clear_screen()
                zip_path = download_branch(branch_name)
            break
        elif choice in ("n", "no"):
            print("\nOperation cancelled.")
            return
        else:
            print("Please enter y or n.")

    
    # Then extract and build
    clear_screen()
    source_folder = extract_zip(zip_path)
    solution = find_solution(source_folder)
    msbuild = find_msbuild()
    build_solution(msbuild, solution)
    sync_to_script_dir(source_folder, branch_name)

    shutil.rmtree(WORK_DIR)
    save_version(remote_sha)
    clear_screen()
    print("\nUpdate/Rebuild completed successfully.")


# added this to stopit from autoclosing
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        print("\nPress Enter to exit...")
        input()
        sys.exit()
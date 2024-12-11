import PyInstaller.__main__
import sys
import platform
import os
import shutil

def clean_build_dirs():
    """Clean up build directories"""
    dirs_to_clean = ['build', 'dist']
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d)

def main():
    # Create build directory if it doesn't exist
    build_dir = 'build'
    os.makedirs(build_dir, exist_ok=True)

    # Determine executable extension based on platform
    sys_platform = platform.system().lower()
    exe_extension = '.exe' if sys_platform == 'windows' else ''
    
    # Clean previous build files
    clean_build_dirs()

    # Run PyInstaller
    PyInstaller.__main__.run([
        'create-amis.py',
        '--onefile',
        '--name=aws-synced-ami-creator' + exe_extension,
        '--clean',
        '--log-level=WARN',
        f'--specpath={build_dir}',
        '--workpath=build/temp',
        '--distpath=dist'
    ])

if __name__ == "__main__":
    main() 
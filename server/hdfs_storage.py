import shutil
import subprocess
import tempfile
from pathlib import Path


def upload_to_hdfs(local_file, hdfs_path):
    local_path = Path(local_file).resolve()

    subprocess.run([
        "hdfs",
        "dfs",
        "-mkdir",
        "-p",
        hdfs_path
    ])

    with tempfile.TemporaryDirectory(prefix="bdtelmvp_hdfs_") as temp_dir:
        staged_file = Path(temp_dir) / local_path.name
        shutil.copy2(local_path, staged_file)

        subprocess.run([
            "hdfs",
            "dfs",
            "-put",
            "-f",
            str(staged_file),
            hdfs_path
        ])


def list_hdfs_path(hdfs_path):
    result = subprocess.run(
        [
            "hdfs",
            "dfs",
            "-ls",
            hdfs_path
        ],
        capture_output=True,
        text=True
    )

    return result


def count_hdfs_files(hdfs_path):
    result = subprocess.run(
        [
            "hdfs",
            "dfs",
            "-ls",
            "-R",
            hdfs_path
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return 0

    return sum(
        1
        for line in result.stdout.splitlines()
        if line.startswith("-")
    )

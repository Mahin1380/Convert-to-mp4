from pathlib import Path
import os
from send2trash import send2trash
from better_ffmpeg_progress import FfmpegProcess, FfmpegProcessError
# === CONFIG ===
source_folder = Path(r"C:\Users\Mahin\Downloads\Video")
use_qsv_encode = False  # Set to True to re-encode using Intel QSV

for folder, subfolders, file_names in os.walk(source_folder):
    for file_name in file_names:
        if file_name.lower().endswith(".ts"):
            ts_file = Path(folder) / file_name
            mp4_file = ts_file.with_suffix(".mp4")

            if mp4_file.exists():
                print(f"Skipping {ts_file} because {mp4_file} already exists")
                continue

            # Build ffmpeg command
            if use_qsv_encode:
                cmd = [
                    "ffmpeg",
                    "-hwaccel", "qsv",
                    "-i", str(ts_file),
                    "-c:v", "h264_qsv",
                    "-preset", "fast",  # optional: faster encode
                    "-c:a", "aac",
                    str(mp4_file)
                ]
            else:
                # Fast remux: copy video, re-encode audio
                cmd = [
                    "ffmpeg",
                    "-i", str(ts_file),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    str(mp4_file)
                ]

            try:
               process = FfmpegProcess(cmd)
               process.run()
            except FfmpegProcessError as e:
                print(f"Error converting {ts_file}: {e}")
            finally:
                send2trash(str(ts_file))
                print(f"Converted and trashed {ts_file}")

print("All conversions completed.")

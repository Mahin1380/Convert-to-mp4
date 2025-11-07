from pathlib import Path
import os
import re
import time
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from rich import print
from send2trash import send2trash
from better_ffmpeg_progress import FfmpegProcess, FfmpegProcessError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

source_folder = Path(r"C:\Users\Mahin\Downloads\Video")

paths = [
    source_folder,
    Path(r"C:\Users\Mahin\code\Python Files"),
    Path(r"C:\Users\Mahin\OneDrive\Desktop"),
    Path(r"C:\Users\Mahin\code"),
    Path(r"E:\Video"),
]

max_workers = 4


def clean_log_txt_files(folder: Path):
    """Delete all .ts_ffmpeg_log.txt files in the folder."""
    for file in folder.glob("*.ts_ffmpeg_log.txt"):
        try:
            send2trash(str(file))
            print(f"[green]Moved {file.name} to Recycle Bin.[/green]")
        except Exception as e:
            print(f"[red]Error deleting {file.name}: {e}[/red]")


def rename_file(mp4_file: Path):
    """
    Rename an .mp4 file if its stem matches the regex pattern.
    Examples:
      "recording-01.mp4"     → "recording.mp4"
      "meeting-room-23.mp4"  → "meeting-room.mp4"
    """
    patterns = [
        r'\w+-\d+',        
        r'\w+-\w+-\d+',
        r'\w+ \w+ \d+'     
    ]

    base_name = None
    for pattern in patterns:
        match = re.match(pattern, mp4_file.stem)
        if match:
            base_name = match.group(0)  # group 0 contains the part we want
            break

    if base_name:
        cleaned_name = base_name + mp4_file.suffix
        new_file = mp4_file.with_name(cleaned_name)

        if new_file.exists():
            print(f"[yellow]Skipping rename: {new_file.name} already exists.[/yellow]")
            return mp4_file

        try:
            mp4_file.rename(new_file)
            print(f"[green]Renamed {mp4_file.name} → {new_file.name}[/green]")
            return new_file
        except Exception as e:
            print(f"[red]Error renaming {mp4_file.name}: {e}[/red]")
            return mp4_file
    else:
        print(f"[blue]No rename needed for {mp4_file.name}[/blue]")
        return mp4_file


def convert_to_mp4_file(ts_file: Path):
    """Convert a single .ts file to .mp4 and move original to Recycle Bin."""
    mp4_file = ts_file.with_suffix(".mp4")
    original_stem = ts_file.stem

    if len(original_stem) > 150:
        try:
            truncated_stem = original_stem[:150]
            truncated_ts = ts_file.with_name(truncated_stem + ts_file.suffix)
            print(f"[yellow]Filename too long, truncating: {ts_file.name}[/yellow]")
            os.rename(ts_file, truncated_ts)
            ts_file = truncated_ts
            print(f"[green]Renamed to: {ts_file.name}[/green]")
        except Exception as e:
            print(f"[red]Error truncating filename: {e}[/red]")
            return

    if mp4_file.exists():
        print(f"[yellow]Skipping {ts_file.name}, {mp4_file.name} already exists.[/yellow]")
        return

    cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "qsv",
        "-hwaccel_output_format", "qsv",
        "-i", str(ts_file),
        "-c:v", "h264_qsv",
        "-preset", "faster",
        "-look_ahead", "0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-avoid_negative_ts", "make_zero",
        str(mp4_file),
    ]

    print(f"[blue]Converting {ts_file.name} to {mp4_file.name}...[/blue]")
    try:
        process = FfmpegProcess(cmd)
        process.run()
        print(f"[green]Successfully converted {ts_file.name} → {mp4_file.name}[/green]")
        send2trash(str(ts_file))
        print(f"[green]Moved {ts_file.name} to Recycle Bin.[/green]")
        rename_file(mp4_file)
        time.sleep(1)
        for path in paths:
            clean_log_txt_files(path)
        print("[cyan]Looking for new files...[/cyan]")
    except FfmpegProcessError as e:
        print(f"[red]Error converting {ts_file.name}: {e}[/red]")


def convert_existing_ts_files(folder: Path):
    """Convert all existing .ts files in the folder."""
    ts_files = list(folder.glob("*.ts"))
    if not ts_files:
        print(f"[blue]No .ts files found in {folder}.[/blue]")
        return

    print(f"[bold green]Found {len(ts_files)} .ts files in {folder} to convert.[/bold green]")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(convert_to_mp4_file, ts_files)


class MyHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.processing_files = set()

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".ts"):
            return

        ts_file = Path(event.src_path)
        if str(ts_file) in self.processing_files:
            return

        self.processing_files.add(str(ts_file))
        print(f"[cyan]Detected new .ts file: {ts_file}[/cyan]")
        time.sleep(0.5)

        def convert_and_cleanup():
            try:
                convert_to_mp4_file(ts_file)
            finally:
                self.processing_files.discard(str(ts_file))

        Thread(target=convert_and_cleanup, daemon=True).start()


if __name__ == "__main__":
    for path in paths:
        if path.exists():
            convert_existing_ts_files(path)

    event_handler = MyHandler()
    observer = Observer()

    for path in paths:
        if path.exists():
            observer.schedule(event_handler, str(path), recursive=False)
            print(f"[green]Monitoring: {path}[/green]")
        else:
            print(f"[yellow]Skipping non-existent path: {path}[/yellow]")

    observer.start()
    print("[green]Watching for new .ts files...[/green]")
    print("[yellow]Press Ctrl+C to stop.[/yellow]")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[yellow]Stopping monitoring...[/yellow]")
        observer.stop()
        observer.join()

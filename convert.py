from pathlib import Path
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
import re
import time
from shutil import move
from concurrent.futures import ThreadPoolExecutor
from rich import print
from better_ffmpeg_progress import FfmpegProcess
from send2trash import send2trash
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import ffmpeg  # pip install ffmpeg-python

source_folders = [
    Path(r"E:\Video"),
    Path(r"F:\Movies")
]

MAX_WORKERS = 4

log_folders = [
    Path(r"C:\Users\Mahin\OneDrive\Desktop"),
    Path(r"C:\Users\Mahin\code"),
]

target_folder = Path(r"E:\Output")

hb_path = r"C:\Users\Mahin\Downloads\Compressed\HandBrakeCLI-1.11.2-win-x86_64\HandBrakeCLI.exe"


def shorten_file_name(ts_file: Path) -> Path:
    original_stem = ts_file.stem
    if len(original_stem) <= 150:
        return ts_file

    try:
        shortened_stem = original_stem[:150]
        new_file = ts_file.with_name(shortened_stem + ts_file.suffix)
        print(f"[yellow]Shortening: {ts_file.name}[/yellow]")
        ts_file.rename(new_file)
        print(f"[green]Renamed to: {new_file.name}[/green]")
        return new_file
    except Exception as e:
        print(f"[red]Error shortening filename: {e}[/red]")
        return ts_file


def get_video_duration(file_path: Path) -> float:
    """Get duration in seconds using ffmpeg-python"""
    try:
        metadata = ffmpeg.probe(str(file_path))
        return float(metadata['format']['duration'])
    except Exception:
        return 0.0


def clean_log_txt_files(folders: list[Path]):
    for folder in folders:
        for file in folder.glob("*.ts_ffmpeg_log.txt"):
            try:
                send2trash(str(file))
                print(f"[green]Moved {file.name} to Recycle Bin.[/green]")
            except Exception as e:
                print(f"[red]Error deleting {file.name}: {e}[/red]")


def convert_to_mp4(ts_file: Path):
    mp4_file = ts_file.with_suffix(".mp4")
    if mp4_file.exists():
        print("[yellow]MP4 already exists[/yellow]")
        return mp4_file

    original_duration = get_video_duration(ts_file)
    print(f"[blue]Processing {ts_file.name}...[/blue]")

    # 1. Try fast FFmpeg first
    try:
        cmd = [
        "ffmpeg",
        "-y",                 # overwrite
        "-i", str(ts_file),
        "-c", "copy",          # NO re-encode (fast)
        str(mp4_file)
    ]
        process = FfmpegProcess(cmd)
        process.run()

        new_duration = get_video_duration(mp4_file)
        if abs(original_duration - new_duration) < 10:
            print("[green]✅ Fast FFmpeg copy successful[/green]")
            send2trash(str(ts_file))
            return mp4_file
    except Exception:
        pass

    # 2. HandBrake with Rich Progress Bar
    print("[blue]Starting HandBrake (this may take a while)...[/blue]")

    hb_cmd = [
        hb_path,
        "--input", str(ts_file),
        "--output", str(mp4_file),
        "--preset", "Very Fast 1080p30",
        "--quality", "22",
        "--encoder", "x264",
        "--optimize",
        "--all-audio",
        "--aencoder", "aac",
        "--ab", "160"
    ]

    progress_pattern = re.compile(r'(\d+\.\d+)\s*%')

    try:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>5.1f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            refresh_per_second=10,
        ) as progress:

            task = progress.add_task(
                f"Encoding {ts_file.name}",
                total=100
            )

            process = subprocess.Popen(
                hb_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in process.stdout:
                match = progress_pattern.search(line)
                if match:
                    percent = float(match.group(1))
                    progress.update(task, completed=percent)

            process.wait()
            progress.update(task, completed=100)

            if process.returncode == 0 and mp4_file.exists():
                print("[green]✅ HandBrake conversion finished successfully[/green]")
                send2trash(str(ts_file))
                return mp4_file
            else:
                print(f"[red]HandBrake failed with code {process.returncode}[/red]")
                return None

    except Exception as e:
        print(f"[red]Error during HandBrake: {e}[/red]")
        return None


def rename_file(mp4_file: Path):
    patterns = [r'\w+-\w+-\d+', r'\w+ \w+ \d+', r'\w+-\d+', r'\w+ \d+']
    base_name = None
    for pattern in patterns:
        match = re.findall(pattern, mp4_file.stem)
        if match:
            base_name = match[0]
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
            print(f"[red]Rename error: {e}[/red]")
            return mp4_file
    return mp4_file


def move_converted_files(mp4_file: Path, target_folder: Path):
    target_folder.mkdir(exist_ok=True, parents=True)
    target_file = target_folder / mp4_file.name

    if target_file.exists():
        print(f"[yellow]Target file already exists: {target_file.name}[/yellow]")
        return target_file

    try:
        move(str(mp4_file), str(target_file))
        print(f"[green]Moved → {target_folder}[/green]")
        return target_file
    except Exception as e:
        print(f"[red]Move error: {e}[/red]")
        return mp4_file


def process_single_file(ts_file: Path):
    shortened_file = shorten_file_name(ts_file)
    mp4_file = convert_to_mp4(shortened_file)
    if mp4_file is None:
        return

    renamed_file = rename_file(mp4_file)
    move_converted_files(renamed_file, target_folder)
    time.sleep(1)
    clean_log_txt_files(log_folders)


# ... rest of your code (TSFileHandler, main(), etc.) remains the same ...

class TSFileHandler(FileSystemEventHandler):

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
        time.sleep(1)

        try:
            process_single_file(ts_file)
        finally:
            self.processing_files.discard(str(ts_file))

def main():
    # get video files from source folders
    ts_files = [file for folder in source_folders for file in folder.glob("*.ts")]
    # check if source folder exists
    for folder in source_folders:
        if not folder.exists():
            print(f"[red]Source folder doesn't exist: {folder}[/red]")
            return
    
    # process existing files first
    if ts_files:
        print(f"[bold green]Processing {len(ts_files)} existing files...[/bold green]")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            executor.map(process_single_file, ts_files)
        print("[green]Finished processing existing files![/green]")
       
    else:
        print("[blue]No existing .ts files found.[/blue]")
        
    # start watching
    for folder in source_folders:
        print(f"[bold cyan]Now monitoring {folder} for new .ts files...[/bold cyan]")
        event_handler = TSFileHandler()
        observer = Observer()
        observer.schedule(event_handler, str(folder), recursive=False)
        observer.start()
    print("[yellow]Press Ctrl+C to stop...[/yellow]")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[yellow]Stopping...[/yellow]")
        observer.stop()
        observer.join()
        print("[green]Stopped! ✨[/green]")

if __name__ == "__main__":
    main()

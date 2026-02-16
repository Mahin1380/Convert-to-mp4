from pathlib import Path
import re
import time
from shutil import move
from concurrent.futures import ThreadPoolExecutor
from rich import print
from better_ffmpeg_progress import FfmpegProcess , FfmpegProcessError
from send2trash import send2trash
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

source_folders = [
                    Path(r"E:\Video"),
                    Path(r"F:\Movies")
                
                ]
MAX_WORKERS = 4

ts_files = [file for folder in source_folders for file in folder.glob("*.ts")]
log_folders = [

                Path(r"C:\Users\Mahin\OneDrive\Desktop"),
                Path(r"C:\Users\Mahin\code"),
    
                ]

target_folder = Path(r"E:\Output")

def shorten_file_name(ts_file: Path) -> Path:
    """Shorten filename if it exceeds 150 characters."""
    original_stem = ts_file.stem

    if len(original_stem) <= 150:
        return ts_file  # no need to shorten

    try:
        shortened_stem = original_stem[:150]
        new_file = ts_file.with_name(shortened_stem + ts_file.suffix)
        print(f"[yellow]Shortening: {ts_file.name}[/yellow]")
        ts_file.rename(new_file)
        print(f"[green]Renamed to: {new_file.name}[/green]")
        return new_file
    except Exception as e:
        print(f"[red]Error shortening filename: {e}[/red]")
        return ts_file  # return original if failed

def clean_log_txt_files(folders: list[Path]):
    """Delete all .ts_ffmpeg_log.txt files in the folders."""
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
        print("[yellow]This file already exists[/yellow]")
        return 
    
    cmd = [
        "ffmpeg",
        "-y",                 # overwrite
        "-i", str(ts_file),
        "-c", "copy",          # NO re-encode (fast)
        str(mp4_file)
    ]



    print(f"[blue]Converting {ts_file.name} to {mp4_file.name}...[/blue]")
    
    try:
        process = FfmpegProcess(cmd)
        process.run()
        print(f"[green]Successfully converted {ts_file.name} → {mp4_file.name}[/green]")
        send2trash(str(ts_file))
        return mp4_file
    except FfmpegProcessError as e:
        print(f"[red]Error converting {ts_file.name}: {e}[/red]")
        return None

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
        r'\w+ \w+ \d+',
        r'\w+ \d+'     
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
            print(f"[green]Renamed {mp4_file.name}[/green] → [orange]{new_file.name}[/orange]")
            return new_file
        except Exception as e:
            print(f"[red]Error renaming {mp4_file.name}: {e}[/red]")
            return mp4_file
    else:
        print(f"[blue]No rename needed for {mp4_file.name}[/blue]")
        return mp4_file

def move_converted_files(mp4_file: Path, target_folder: Path):
    """Move converted mp4 file to target folder."""
    target_folder.mkdir(exist_ok=True, parents=True)
    
    target_file = target_folder / mp4_file.name
    
    if target_file.exists():
        print(f"[yellow]File already exists in target: {target_file.name}[/yellow]")
        return target_file
    
    try:
        move(str(mp4_file), str(target_file))  # use full paths
        print(f"[green]Moved {mp4_file.name} → {target_folder}[/green]")
        return target_file
    except Exception as e:
        print(f"[red]Error moving file: {e}[/red]")
        return mp4_file


def process_single_file(ts_file: Path):
    """Process one ts file through full pipeline."""

    shortened_file = shorten_file_name(ts_file)
    mp4_file = convert_to_mp4(shortened_file)
    if mp4_file is None:
        return
    
    renamed_file = rename_file(mp4_file)
    move_converted_files(renamed_file, target_folder)
    time.sleep(1)
    clean_log_txt_files(log_folders)
    


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

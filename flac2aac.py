#!/usr/bin/env python
import os
import subprocess
import configparser
from tqdm import tqdm
import re
from ffmpeg_progress_yield import FfmpegProgress


config = configparser.ConfigParser()
config.read('config.ini')

flac_folder = config['DEFAULT']['flac_folder']
destination_folder = config['DEFAULT']['destination_folder']
delete_flac = config.getboolean('DEFAULT', 'delete_flac')
metadata_comment = config['DEFAULT']['metadata_comment']
encoder = config['DEFAULT']['encoder']
bitrate = config['DEFAULT']['bitrate']

new_file_extension = 'm4a'
# overall_progress = None
# inner_progress = None

def convert_to_m4a(file_path, file_name, file_extension):
    ffmpeg_command = [
        "ffmpeg", "-y", "-i", f"{file_path}/{file_name}.{file_extension}",
        "-c:v", "copy", "-vsync", "2", "-c:a", f"{encoder}",
        "-b:a", f"{bitrate}k", "-metadata", f"comment={metadata_comment}",
        f"{file_path}/{file_name}.{new_file_extension}"
    ]

    ff = FfmpegProgress(ffmpeg_command)
    inner_progress = tqdm(total=100, position=1, desc=file_name, leave=False)
    with inner_progress as pbar:
        for progress in ff.run_command_with_progress():
            pbar.update(progress - pbar.n)
    # for progress in ff.run_command_with_progress():
    #     print(f"{progress}/100")
    # subprocess.run(ffmpeg_command, stderr=subprocess.PIPE, check=True)


    # with open("progress.log", "w") as logfile:
    #     # os.system(f"ffmpeg -y -i '{file_path}/{file_name}.{file_extension}' -c:v copy -vsync 2 -c:a {encoder} -b:a {bitrate}k '{file_path}/{file_name}.{new_file_extension}' 2>&1 | tee progress.log")
    #     os.system(f"ffmpeg -y -i '{file_path}/{file_name}.{file_extension}' -c:v copy -vsync 2 -c:a {encoder} -b:a {bitrate}k '{file_path}/{file_name}.{new_file_extension}' -progress progress.log 2>&1")

    # with open("progress.log", "r") as logfile:
    #     for line in logfile:
    #         match = re.search("time=([0-9.:]+) bitrate=", line)
    #         if match:
    #             current_time = match.group(1)
    #             tqdm.write(f'Converted: {file_path}/{file_name}.{file_extension} Time: {current_time}')

    if delete_flac == True:
        os.remove(f"{file_path}/{file_name}.{file_extension}")

def move_to_destination(file_path, file_name, file_extension):
    os.rename(f"{file_path}/{file_name}.{file_extension}", f"{destination_folder}/{file_name}.{file_extension}")

def main():
    files_to_process = []
    for root, dirs, files in os.walk(flac_folder):
        for file in files:
            if file.endswith(".flac"):
                files_to_process.append(os.path.join(root, file))

    for file in tqdm(files_to_process, desc='Converting Files'):
        file_path, file_name_with_extension = os.path.split(os.path.join(root, file))
        file_name, file_extension = os.path.splitext(file_name_with_extension)

        lossless_file = os.path.join(root, file)
        m4a_file = os.path.splitext(lossless_file)[0] + f".{new_file_extension}"
        m4a_file = os.path.join(destination_folder, os.path.relpath(m4a_file, flac_folder))

        convert_to_m4a(file_path, file_name, file_extension[1:])
        if flac_folder != destination_folder:
            move_to_destination(file_path, file_name, f"{new_file_extension}")
    # nzbpp_directory = os.environ.get("NZBPP_DIRECTORY")
    # move_to_itunes_folder = os.environ.get("NZBPO_MOVETOITUNESFOLDER", "no")
    # os.chdir(nzbpp_directory)
    # for root, dirs, files in os.walk(flac_folder):
    # # for root, dirs, files in os.walk("."):
    #     for file in files:
    #         if file.endswith((".flac", ".wav")):
    #             file_path, file_name_with_extension = os.path.split(os.path.join(root, file))
    #             file_name, file_extension = os.path.splitext(file_name_with_extension)

    #             lossless_file = os.path.join(root, file)
    #             m4a_file = os.path.splitext(lossless_file)[0] + f".{new_file_extension}"
    #             m4a_file = os.path.join(destination_folder, os.path.relpath(m4a_file, flac_folder))

    #             convert_to_m4a(file_path, file_name, file_extension[1:])
    #             if flac_folder != destination_folder:
    #                 move_to_destination(file_path, file_name, f"{new_file_extension}")
    exit(93)

if __name__ == "__main__":
    main()
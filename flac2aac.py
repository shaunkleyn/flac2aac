#!/usr/bin/env python
import os
import subprocess
import configparser

config = configparser.ConfigParser()
config.read('config.ini')

flac_folder = config['DEFAULT']['flac_folder']
destination_folder = config['DEFAULT']['destination_folder']
delete_flac = config.getboolean('DEFAULT', 'delete_flac')
move_to_itunes_folder = config.getboolean('DEFAULT', 'move_to_itunes_folder')
metadata_comment = config.getboolean('DEFAULT', 'metadata_comment')
encoder = config.getboolean('DEFAULT', 'encoder')
bitrate = config.getboolean('DEFAULT', 'bitrate')

new_file_extension = 'm4a'

def convert_to_m4a(file_path, file_name, file_extension):
    ffmpeg_command = [
        "ffmpeg", "-y", "-i", f"{file_path}/{file_name}.{file_extension}",
        "-c:v", "copy", "-vsync", "2", "-c:a", f"{encoder}",
        "-b:a", f"{bitrate}k", "-metadata", f"comment={metadata_comment}",
        f"{file_path}/{file_name}.{new_file_extension}"
    ]
    subprocess.run(ffmpeg_command, stderr=subprocess.PIPE, check=True)
    if delete_flac == True:
        os.remove(f"{file_path}/{file_name}.{file_extension}")

def move_to_destination(file_path, file_name, file_extension):
    os.rename(f"{file_path}/{file_name}.{file_extension}", f"{destination_folder}/{file_name}.{file_extension}")

def main():
    # nzbpp_directory = os.environ.get("NZBPP_DIRECTORY")
    # move_to_itunes_folder = os.environ.get("NZBPO_MOVETOITUNESFOLDER", "no")
    # os.chdir(nzbpp_directory)
    for root, dirs, files in os.walk(flac_folder):
    # for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith((".flac", ".wav")):
                file_path, file_name_with_extension = os.path.split(os.path.join(root, file))
                file_name, file_extension = os.path.splitext(file_name_with_extension)

                lossless_file = os.path.join(root, file)
                m4a_file = os.path.splitext(lossless_file)[0] + f".{new_file_extension}"
                m4a_file = os.path.join(destination_folder, os.path.relpath(m4a_file, flac_folder))

                convert_to_m4a(file_path, file_name, file_extension[1:])
                if move_to_itunes_folder == True:
                    move_to_destination(file_path, file_name, f"{new_file_extension}")
    exit(93)

if __name__ == "__main__":
    main()
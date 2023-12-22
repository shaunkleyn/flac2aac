#!/usr/bin/env python
import os
import subprocess
import configparser
from tqdm import tqdm
import re
from ffmpeg_progress_yield import FfmpegProgress
import logging
import traceback
import shutil
from mutagen.mp4 import MP4, MP4Cover
from argparse import ArgumentParser


config = configparser.ConfigParser()
config.read('config.ini', 'utf8')

# Exit codes:
#  0 - success; or test
#  1 - no audio tracks detected
#  2 - ffmpeg not found
#  3 - invalid command line arguments
#  4 - log file is not writable
#  5 - specified audio file not found
#  6 - error when creating output directory
#  7 - unknown eventtype environment variable
# 10 - a general error occurred in file conversion loop; check log
# 11 - source and destination have the same file name
# 12 - ffprobe returned an error
# 13 - ffmpeg returned an error
# 14 - the new file could not be found or is zero bytes
# 15 - could not set permissions and/or owner on new file
# 16 - could not delete the original file
# 17 - Lidarr API error
# 18 - Lidarr job timeout
# 20 - general error

source_folder = config['DEFAULT']['source_folder']
destination_folder = config['DEFAULT']['destination_folder']
other_files_dir = config['DEFAULT']['other_files_dir']
# delete_original_file = config.getboolean('DEFAULT', 'delete_original_file')
metadata_comment = config['DEFAULT']['metadata_comment']
encoder = config['DEFAULT']['encoder']
bitrate = config['DEFAULT']['bitrate']


def string2RawString(string):
    rawString = ''
    for i in string.split('\\'):
        rawString = rawString+("%r"%i).strip("'")+"\\"
    return rawString

source_folder = config['SOURCE']['folder']
delete_original_file = config.getboolean('SOURCE', 'delete_original_file')
empty_original_file = config.getboolean('SOURCE', 'empty_original_file')

new_file_extension = config['TARGET']['format']
encoder = config['TARGET']['encoder']
bitrate = config['TARGET']['bitrate']
destination_folder = config['TARGET']['folder']

#parser = ArgumentParser()
#parser.add_argument("-f", "--folder", dest="directory", help="Folder containing items to normalize")
#parser.add_argument("-c", "--compression", dest="compression", help="The compression config to apply")
#args = parser.parse_args()
#directory = args.directory
#compression = args.compression

if destination_folder == '':
    destination_folder = source_folder


logging.basicConfig(filename='log.txt', encoding='utf-8', level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
# create logger
logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)


audio_extensions = [".flac", ".wav"]
audio_to_move = ['.mp3','.m4a']
extensions_to_move = ['.png', '.jpg', '.jpeg']

# overall_progress = None
# inner_progress = None
logger.debug("OPTIONS:")
logger.debug(f'Source folder: {source_folder}')
logger.debug(f'Destination folder: {destination_folder}')
logger.debug(f'Delete Source file: {delete_original_file}')

def add_cover_art(file):
    file_path, file_name_with_extension = os.path.split(file)
    cover_art = ''
    if os.path.exists(os.path.join(file_path, 'front.jpg')):
        cover_art = os.path.join(file_path, 'front.jpg')

    if os.path.exists(os.path.join(file_path, 'front.png')):
        cover_art = os.path.join(file_path, 'front.png')

    if os.path.exists(os.path.join(file_path, 'folder.jpg')):
        cover_art = os.path.join(file_path, 'front.jpg')
    if os.path.exists(os.path.join(file_path, 'folder.png')):
        cover_art = os.path.join(file_path, 'front.png')

    if os.path.exists(os.path.join(file_path, 'cover.jpg')):
        cover_art = os.path.join(file_path, 'cover.jpg')
    if os.path.exists(os.path.join(file_path, 'cover.png')):
        cover_art = os.path.join(file_path, 'cover.png')


    if cover_art != '':
        logger.info(f'Adding cover art: {cover_art}')
        video = MP4(file)
        if 'jpg' in cover_art:
            with open(cover_art, "rb") as f:
                video["covr"] = [
                    MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)
                ]
        elif 'png' in cover_art:
            with open(cover_art, "rb") as f:
                video["covr"] = [
                    MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_PNG)
                ]

        video.save()


def convert_to_m4a(file_path, file_name, file_extension):
    input_path =  os.path.normpath(f"{file_path}\{file_name}.{file_extension}")
    output_path =  os.path.normpath(f"{file_path}\{file_name}.{new_file_extension}")
    logger.debug(f'Converting {input_path} to \n\t{output_path}...')
    ffmpeg_command = [
        "ffmpeg", "-hide_banner", "-y", "-i", f"{input_path}",
        "-c:v", "copy", "-vsync", "2", "-c:a", f"{encoder}",
        "-ar", "44100",
        "-b:a", f"{bitrate}k", "-metadata", f"comment={metadata_comment}",
        f"{output_path}"
    ]

    ffmpeg_command2 = ['ffmpeg.exe', '-y', '-hide_banner', "-loglevel", "error", '-stats', 
                      '-i', f"{input_path}", '-vf', 'crop=((in_w/2)*2):((in_h/2)*2)', 
                      '-c:a', f'{encoder}', 
                      '-ar', '44100',
                      '-b:a', f'{bitrate}k', 
                      '-metadata', f'comment={metadata_comment}',
                      f"{output_path}"]
 
    logger.info(ffmpeg_command)
    try:
        result = subprocess.run(ffmpeg_command, shell=True)
        if result.returncode == 0:
            add_cover_art(output_path)
        # ff = FfmpegProgress(ffmpeg_command)
        # inner_progress = tqdm(total=100, position=1, desc=file_name, leave=False)
        # with inner_progress as pbar:
        #     for progress in ff.run_command_with_progress():
        #         pbar.update(progress - pbar.n)

        # get the output
        #print(ff.stderr)
            if empty_original_file == True:
                empty_file(input_path)
            if delete_original_file == True:
                logger.debug(f"Deleting { input_path}")
                os.remove(input_path)

        return True
    except Exception as e:
        logger.error(traceback.format_exc())
        return False

def empty_file(filepath):
    open(filepath, 'w').close()

def move_to_destination(file_path, file_name, file_extension):
    logger.debug(f'Moving {file_path}\{file_name}.{file_extension} to {destination_folder}\{file_name}.{file_extension}')
    try:
        shutil.move(os.path.normpath(f"{file_path}\{file_name}.{file_extension}"), os.path.normpath(f"{destination_folder}\{file_name}.{file_extension}"))
        #os.rename(os.path.normpath(f"{file_path}\{file_name}.{file_extension}"), os.path.normpath(f"{destination_folder}\{file_name}.{file_extension}"))
        logger.debug('Move successful')
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(f'Could not move file: {e}')

def move(source, destination):
    file_path, file_name_with_extension = source
    file_name, file_extension = os.path.splitext(file_name_with_extension)
    logger.debug(f'Moving other file: {file_path}\{file_name_with_extension} to {destination}\{file_name_with_extension}')
    try:
        shutil.move(os.path.normpath(f"{file_path}\{file_name_with_extension}"), os.path.normpath(f"{destination}\{file_name_with_extension}"))
        #os.rename(os.path.normpath(f"{file_path}\{file_name}.{file_extension}"), os.path.normpath(f"{destination_folder}\{file_name}.{file_extension}"))
        logger.debug('Move successful')
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(f'Could not move file: {e}')

def main():
    files_to_process = []
    files_to_move = []
    logger.debug('Scanning for files...')
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            #if file.endswith(".flac", ".wav"):
            if any(file.endswith(ext) for ext in audio_extensions):
                files_to_process.append(os.path.normpath(os.path.join(root, file)))
                #print(os.path.normpath(os.path.join(root, file)))
            elif any(file.endswith(ext) for ext in extensions_to_move):
                file_path, file_name_with_extension = os.path.split(os.path.join(root, file))
                file_name, file_extension = os.path.splitext(file_name_with_extension)
                dir = os.path.basename(root)
                if 'abc' in file:
                    new_file = f'{dir}-{file_name}{file_extension}'
                    os.rename(os.path.join(root, file), os.path.join(root, f'{dir}-{file_name}{file_extension}'))
                    move(os.path.split(os.path.join(root, f'{dir}-{file_name}{file_extension}')), other_files_dir)
            #elif any(file.endswith(ext) for ext in audio_to_move):
            #    move(os.path.split(os.path.join(root, file)), destination_folder)

    
    logger.debug(f'Found {len(files_to_process)} files to convert')

    for file in tqdm(files_to_process, desc='Converting Files'):
        print('------------------------------------------------')
        file_path, file_name_with_extension = os.path.split(os.path.join(root, file))
        file_name, file_extension = os.path.splitext(file_name_with_extension)

        lossless_file = os.path.join(root, file)
        if os.path.getsize(lossless_file) > 1:
            m4a_file = os.path.splitext(lossless_file)[0] + f".{new_file_extension}"
            m4a_file = os.path.join(destination_folder, os.path.relpath(m4a_file, source_folder))
            try:
                if (convert_to_m4a(file_path, file_name, file_extension[1:]) == True):
                    logger.debug('Conversion successful')
                    if source_folder != destination_folder:
                        move_to_destination(file_path, file_name, f"{new_file_extension}")
                        
            except:
                print(F'Could not convert {m4a_file}')
                logger.error(F'Could not convert {m4a_file}')
    # nzbpp_directory = os.environ.get("NZBPP_DIRECTORY")
    # move_to_itunes_folder = os.environ.get("NZBPO_MOVETOITUNESFOLDER", "no")
    # os.chdir(nzbpp_directory)
    # for root, dirs, files in os.walk(source_folder):
    # # for root, dirs, files in os.walk("."):
    #     for file in files:
    #         if file.endswith((".flac", ".wav")):
    #             file_path, file_name_with_extension = os.path.split(os.path.join(root, file))
    #             file_name, file_extension = os.path.splitext(file_name_with_extension)

    #             lossless_file = os.path.join(root, file)
    #             m4a_file = os.path.splitext(lossless_file)[0] + f".{new_file_extension}"
    #             m4a_file = os.path.join(destination_folder, os.path.relpath(m4a_file, source_folder))

    #             convert_to_m4a(file_path, file_name, file_extension[1:])
    #             if source_folder != destination_folder:
    #                 move_to_destination(file_path, file_name, f"{new_file_extension}")
    exit(93)

if __name__ == "__main__":
    main()
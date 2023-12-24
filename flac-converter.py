
from os import getenv
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import configparser
from tqdm import tqdm
from mutagen.mp4 import MP4, MP4Cover
import subprocess
import traceback
import requests
import json
import time
from pyarr import LidarrAPI
from pyarr.lidarr import LidarrCommand





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


# Setup logger
log_file = f"{__file__}_log.txt"
logging.basicConfig(handlers=[RotatingFileHandler(log_file, maxBytes=1000000, backupCount=5)],
                    encoding='utf-8',
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d,%H:%M:%S',
                    level=logging.INFO)

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


# Variables
audio_extensions_to_convert = [".flac", ".wav"]
source_folder = os.path.dirname(os.path.abspath(sys.argv[0])) # use the script directory as default
delete_original_file = False
empty_original_file = False
new_file_extension = 'mp4'
encoder = 'libfdk_aac'
bitrate = 128
destination_folder = os.path.join(source_folder, 'converted')
metadata_comment = 'Converted by flac-converter.py'
dry_run = False
config_file = os.path.join(source_folder, 'config.ini')



config = configparser.ConfigParser()
config.read(config_file)

# configuration
lidarr_ip = config['LIDARR']['url']
lidarr_port = config['LIDARR']['port']
lidarr_api_token = config['LIDARR']['api_key']
lidarr_eventtype = ''
lidarr_url2 = f'{lidarr_ip}:{lidarr_port}'
lidarr_url = f'{lidarr_ip}:{lidarr_port}/api/v1'

lidarr_headers={
            "X-Api-Key": lidarr_api_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

lidarr = LidarrAPI(lidarr_url2, lidarr_api_token)


try:
    source_folder = config['SOURCE']['folder']
    delete_original_file = config.getboolean('SOURCE', 'delete_original_file')
    empty_original_file = config.getboolean('SOURCE', 'empty_original_file')
    audio_extensions_to_convert = [part.replace(".", "").strip() for part in config['SOURCE']['extensions_to_process'].split(",")]
    audio_extensions_to_convert = ['.' + part.strip() if not part.strip().startswith('.') else part.strip() for part in config['SOURCE']['extensions_to_process'].split(",")]

    new_file_extension = config['TARGET']['format']
    destination_folder = config['TARGET']['folder']

    encoder = config['CONVERT']['encoder']
    bitrate = config['CONVERT']['bitrate']
    metadata_comment = config['CONVERT']['metadata_comment']
    dry_run = config.getboolean('CONVERT', 'dry_run')
except Exception as e:
    logger.error(traceback.format_exc())
    logger.error(f'Could not read all configurations: {e}')
    exit(20)

def log(message):
    logger.debug(message)

def empty_file(filepath):
    open(filepath, 'w').close()
    
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
    logger.debug('\tConverting file')
    input_path =  os.path.normpath(f"{file_path}\{file_name}.{file_extension}")
    output_path =  os.path.normpath(f"{file_path}\{file_name}.{new_file_extension}")
    logger.debug(f'\tInput Path: {input_path}')
    logger.debug(f'\tOutput Path {output_path}')
    ffmpeg_command = [
        "ffmpeg", "-hide_banner", "-y", "-i", f"{input_path}",
        "-c:v", "copy", "-vsync", "2", "-c:a", f"{encoder}",
        "-ar", "44100",
        "-b:a", f"{bitrate}k", "-metadata", f"comment={metadata_comment}",
        f"{output_path}"
    ]
    logger.debug(f'\tCommand: {ffmpeg_command}')
    
    # ffmpeg_command2 = ['ffmpeg.exe', '-y', '-hide_banner', "-loglevel", "error", '-stats', 
    #                   '-i', f"{input_path}", '-vf', 'crop=((in_w/2)*2):((in_h/2)*2)', 
    #                   '-c:a', f'{encoder}', 
    #                   '-ar', '44100',
    #                   '-b:a', f'{bitrate}k', 
    #                   '-metadata', f'comment={metadata_comment}',
    #                   f"{output_path}"]
 
    try:
        if dry_run is not None and dry_run:
            logger.debug('This is only a dry run so not converting file')
            return True
        else:
            if os.path.exists(output_path):
                logger.warning(f'{output_path} already exists.  Using existing file')
            else:
                result = subprocess.run(ffmpeg_command, shell=True)
                if result.returncode == 0:
                    add_cover_art(output_path)
            
            if empty_original_file == True:
                empty_file(input_path)
            if delete_original_file == True:
                logger.debug(f"Deleting { input_path}")
                os.remove(input_path)

        return True
    except Exception as e:
        return False

def get_version():
    url = f"{lidarr_url}/system/status"

    log(f"Debug|Getting Lidarr version. Calling Lidarr API using GET and URL '{url}'")

    try:
        response = requests.get(url, headers=lidarr_headers)
        response.raise_for_status()
        flac2mp3_result = response.json()

        log(f"API returned: {flac2mp3_result}")

        if "version" in flac2mp3_result:
            flac2mp3_return = 0
        else:
            flac2mp3_return = 1

    except Exception as e:
        flac2mp3_message = f"[{e.response.status_code}] Request error when calling: '{url}'\nWeb server returned: {e.response.json().get('message', '')}"
        log(f"Error|{flac2mp3_message}")
        print(f"Error|{flac2mp3_message}", file=sys.stderr)
        flac2mp3_return = 1

    return flac2mp3_return

def get_trackfile_info(artist_id, album_id):
    url = f"{lidarr_url}/trackFile?artistId={artist_id}&albumId={album_id}&apikey={lidarr_api_token}"
    data = {
        "albumId": album_id,
        "artistId": artist_id}
    flac2mp3_result = {}
    logger.debug(f"Debug|Getting track file info for album id {album_id}. Calling Lidarr API using GET and URL '{url}?{data}'")

    try:
        response = requests.get(url, headers=lidarr_headers)
        response.raise_for_status()
        flac2mp3_result = response.json()

        logger.debug(f"API returned: {json.dumps(flac2mp3_result)}")
        #found_object = next((obj for obj in flac2mp3_result if obj.get("id") == target_id), None)
        # if flac2mp3_result and isinstance(flac2mp3_result, list) and flac2mp3_result[0].get("id") is not None:
        #     found_object = next((obj for obj in flac2mp3_result if obj.get("id") == target_id), None)
        #     flac2mp3_return = 0
        # else:
        #     flac2mp3_return = 1
        return flac2mp3_result

    except Exception as e:
        flac2mp3_message = f"[{e.response.status_code}] Request error when calling: '{url}?{data}'\nWeb server returned: {e.response.json().get('message', '')}"
        logger.debug(f"Error|{flac2mp3_message}")
        logger.debug(f"Error|{flac2mp3_message}", file=sys.stderr)


    return flac2mp3_result

def delete_track(track_id, file):
    url = f"{lidarr_url}/trackFile/{track_id}"
    result = False
    logger.debug(f"Debug|Deleting or recycling '{track_id}'. Calling Lidarr API using DELETE and URL '{url}'")

    try:
        response = lidarr.delete_track_file(track_id)
        flac2mp3_result = response.json()
        logger.debug(f"API returned: {flac2mp3_result}")
        if not response.ok:
            os.remove(file)

        result = True

    except Exception as e:
        flac2mp3_message = f"[{e.response.status_code}] Request error when calling: '{url}'\nWeb server returned: {e.response.json().get('message', '')}"
        logger.error(f"Error|{flac2mp3_message}")
        logger.error(f"Error|{flac2mp3_message}", file=sys.stderr)
        result = False

    return result

def get_import_info(artist_id, folder_path, downloadId, album_id):
    url = f"{lidarr_url}/manualimport"
    data = {
        "artistId": artist_id,
        "folder": folder_path,
        "filterExistingFiles": "true",
        "replaceExistingFiles": "false"
    }

    lidarr = LidarrAPI(lidarr_url2, lidarr_api_token)

    #lidarr.get_manual_import(downloadId=downloadId, artistId=artist_id)
    try:
        #data = lidarr.post_command(name="RefreshAlbum", )
        #result = lidarr.get_command(id_=data["id"])
        args = {
            "albumId": [album_id],
        }
        # Define the command and additional parameters as keyword arguments
        #command_name = "RefreshAlbum"  # Replace with the actual command name
        #lidarr.post_command(command_name, albumId=[album_id])
        lidarr.post_command(name='RefreshAlbum',data=args)
        #cmd = LidarrCommand(models., album_id )
        #lidarr.post_command(cmd)

    except Exception as e:
        logger.fatal(f'Cant get import info: {e}')
    lidarr.get_manual_import(source_folder)


    log(f"Debug|Getting list of files that can be imported. Calling Lidarr API using GET and URL '{url}?{data}'")

    try:
        response = requests.get(url, headers=lidarr_headers, params=data)
        #response.raise_for_status()
        flac2mp3_result = response.json()

        log(f"API returned: {json.dumps(flac2mp3_result)}")

        flac2mp3_return = 0

    except Exception as e:
        flac2mp3_message = f"[{e.response.status_code}] Request error when calling: '{url}?{data}'\nWeb server returned: {e.response.json().get('message', '')}"
        log(f"Error|{flac2mp3_message}")
        print(f"Error|{flac2mp3_message}", file=sys.stderr)
        flac2mp3_return = 1

    return flac2mp3_return

def check_job(job_id):
    # Exit codes:
    #  0 - success
    #  1 - queued
    #  2 - failed
    #  3 - loop timed out
    # 10 - curl error
    i = 0
    url = f"{lidarr_url}/command/{job_id}"

    log(f"Debug|Checking job {job_id} completion. Calling Lidarr API using GET and URL '{url}'")

    for i in range(1, 16):
        try:
            response = requests.get(url, headers=lidarr_headers)
            response.raise_for_status()
            flac2mp3_result = response.json()

            log(f"API returned: {json.dumps(flac2mp3_result)}")

            # Guard clauses
            status = flac2mp3_result.get("status", "")
            if status == "failed":
                flac2mp3_return = 2
                break
            elif status == "queued":
                flac2mp3_return = 1
                break
            elif status == "completed":
                flac2mp3_return = 0
                break

            # It may have timed out, so let's wait a second
            log("Debug|Job not done. Waiting 1 second.")
            flac2mp3_return = 3
            time.sleep(1)

        except Exception as e:
            flac2mp3_message = f"[{e.response.status_code}] Request error when calling: '{url}'\nWeb server returned: {e.response.json().get('message', '')}"
            log(f"Error|{flac2mp3_message}")
            print(f"Error|{flac2mp3_message}", file=sys.stderr)
            flac2mp3_return = 10
            break

    return flac2mp3_return

def import_tracks(json, album_path):
    url = f"{lidarr_url}/command"
    data = {
        "name": "DownloadedAlbumsScan",
        "path": album_path
    }    
    # data = {
    #     "name": "ManualImport",
    #     "files": json,
    #     "importMode": "auto",
    #     "replaceExistingFiles": False
    # }

    log("Info|Calling Lidarr API to import tracks")
    log(f"Debug|Importing new files into Lidarr. Calling Lidarr API using POST and URL '{url}' with data {data}")

    try:
        response = requests.post(url, headers=lidarr_headers, json=data)
        #if(response.ok):
        #response.raise_for_status()
        flac2mp3_result = response.json()

        log(f"API returned: {flac2mp3_result}")

        flac2mp3_return = 0

    except Exception as e:
        flac2mp3_message = f"[{e.response.status_code}] Request error when calling: '{url}' with data {data}\nWeb server returned: {e.response.json().get('message', '')}"
        log(f"Error|{flac2mp3_message}")
        log(f"Error|{flac2mp3_message}", file=sys.stderr)
        flac2mp3_return = 1

    return flac2mp3_return

def update_database(artist_id, folder_path, track_list):
    flac2mp3_type = os.environ.get("flac2mp3_type", "")
    flac2mp3_keep = int(os.environ.get("flac2mp3_keep", 0))
    flac2mp3_api_url = os.environ.get("flac2mp3_api_url", "")
    lidarr_artist_id = os.environ.get("lidarr_artist_id", "")
    flac2mp3_import_list = os.environ.get("flac2mp3_import_list", "")
    flac2mp3_debug = int(os.environ.get("flac2mp3_debug", 0))
    flac2mp3_track = os.environ.get("flac2mp3_track", "")

    # Check for URL
    if flac2mp3_type == "batch":
        if flac2mp3_debug >= 1:
            logger.debug("Debug|Cannot use API in batch mode.")
    elif flac2mp3_keep == 1:
        logger.debug("Info|Original audio file(s) kept, no database update performed.")
    elif flac2mp3_api_url:
        # Check for artist ID
        if lidarr_artist_id:
            # Remove trailing pipe
            flac2mp3_import_list = flac2mp3_import_list.rstrip("|")
            # flac2mp3_import_list = flac2mp3_import_list.rstrip("|")
            logger.debug(f"Debug|Track import list: \"{flac2mp3_import_list}\"")

            # Scan for files to import into Lidarr
            flac2mp3_import_count = len(flac2mp3_import_list.split("|"))
            if flac2mp3_import_count != 0:
                logger.debug(f"Info|Preparing to import {flac2mp3_import_count} new files. This may take a long time for large libraries.")
                if get_import_info(artist_id, folder_path):
                    # Build JSON data for all tracks
                    if flac2mp3_debug >= 1:
                        logger.debug("Debug|Building JSON data to import")
                    flac2mp3_json = json.dumps([
                        {
                            "path": track["path"],
                            "artistId": int(lidarr_artist_id),
                            "albumId": int(track["albumId"]),
                            "albumReleaseId": track["albumReleaseId"],
                            "trackIds": [int(track["tracks"][0]["id"])],
                            "quality": track["quality"],
                            "disableReleaseSwitching": False
                        }
                        for track in flac2mp3_result
                        if track["path"] in flac2mp3_import_list.split("|")
                    ])

                    # Import new files into Lidarr
                    flac2mp3_result = import_tracks(flac2mp3_json)
                    flac2mp3_return = 0
                    if flac2mp3_return != 0:
                        flac2mp3_message = f"Error|[{flac2mp3_return}] Lidarr error when importing the new tracks!"
                        logger.debug(flac2mp3_message)
                        sys.exit(17)

                    flac2mp3_jobid = flac2mp3_result[0]["id"]

                    # Check status of job
                    check_job()
                    flac2mp3_return = 0
                    if flac2mp3_return != 0:
                        flac2mp3_message = ""
                        if flac2mp3_return == 1:
                            flac2mp3_message = f"Info|Lidarr job ID {flac2mp3_jobid} is queued. Trusting this will complete and exiting."
                            flac2mp3_exitstatus = 0
                        elif flac2mp3_return == 2:
                            flac2mp3_message = f"Warn|Lidarr job ID {flac2mp3_jobid} failed."
                            flac2mp3_exitstatus = 17
                        elif flac2mp3_return == 3:
                            flac2mp3_message = f"Warn|Script timed out waiting on Lidarr job ID {flac2mp3_jobid}. Last status was: {flac2mp3_result[0]['status']}"
                            flac2mp3_exitstatus = 18
                        elif flac2mp3_return == 10:
                            flac2mp3_message = f"Error|Lidarr job ID {flac2mp3_jobid} returned a curl error."
                            flac2mp3_exitstatus = 17

                        logger.debug(flac2mp3_message)
                        sys.exit(flac2mp3_exitstatus)
                else:
                    flac2mp3_message = f"Error|Lidarr error getting import file list in \"{folder_path}\" for artist ID {lidarr_artist_id}"
                    logger.debug(flac2mp3_message)
                    sys.exit(17)
            else:
                flac2mp3_message = "Warn|Didn't find any tracks to import."
                logger.debug(flac2mp3_message)
                sys.exit(17)
        else:
            flac2mp3_message = "Warn|Missing environment variable lidarr_artist_id"
            logger.debug(flac2mp3_message)
            sys.exit(20)
    else:
        flac2mp3_message = "Warn|Unable to determine Lidarr API URL."
        logger.debug(flac2mp3_message)
        sys.exit(20)

def ffprobe(file_path):
    command = [
        "/usr/bin/ffprobe",
        "-hide_banner",
        #f"-loglevel {flac2mp3_ffmpeg_log}",
        "-print_format json=compact=1",
        "-show_format",
        "-show_entries", "format=tags:title,disc,genre",
        f"-i {file_path}"
    ]

    log(f"Debug|Executing: {' '.join(command)}")

    try:
        result = subprocess.run(command, capture_output=True, text=True)
        flac2mp3_ffprobe_json = result.stdout.strip()
        flac2mp3_return = result.returncode

        if flac2mp3_return != 0:
            flac2mp3_message = f"Error|[{flac2mp3_return}] ffprobe error when inspecting track: '{file_path}'"
            log(flac2mp3_message)
            print(flac2mp3_message, file=sys.stderr)

        log(f"ffprobe returned: {flac2mp3_ffprobe_json}")

        if flac2mp3_ffprobe_json:
            flac2mp3_return = 0
        else:
            flac2mp3_return = 1

    except Exception as e:
        flac2mp3_message = f"Error|Exception occurred during ffprobe execution: {e}"
        log(flac2mp3_message)
        print(flac2mp3_message, file=sys.stderr)
        flac2mp3_return = 1

    return flac2mp3_return
  
def processFiles():
    logger.debug('Starting to process files')
    files_to_process = []
    results = {}
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            logger.debug(f'Found file: {file}')
            if any(file.endswith(ext) for ext in audio_extensions_to_convert):
                logger.debug('File matches extensions to convert')
                files_to_process.append(os.path.normpath(os.path.join(root, file)).encode('utf-8'))
                
    for file in tqdm(files_to_process, desc='Converting Files'):
        print('------------------------------------------------')
        file_path, file_name_with_extension = os.path.split(os.path.join(root, file))
        file_name, file_extension = os.path.splitext(file_name_with_extension)

        logger.debug(f'\tPath: {file_path}')
        logger.debug(f'\tFile Name: {file_name}')
        logger.debug(f'\tFile Extension: {file_extension}')
        lossless_file = os.path.join(root, file)
        if os.path.getsize(lossless_file) > 1:
            logger.debug(f'\tFile is not empty')
            m4a_file = os.path.splitext(lossless_file)[0] + f".{new_file_extension}"
            m4a_file = os.path.join(destination_folder, os.path.relpath(m4a_file, source_folder))
            try:
                if (convert_to_m4a(file_path, file_name, file_extension[1:]) == True):
                    results[file] = m4a_file
                    logger.debug('Conversion successful')
                    if delete_original_file == True:
                        logger.debug(f"Deleting {file}")
                        os.remove(file)
                    #if source_folder != destination_folder:
                    #    move_to_destination(file_path, file_name, f"{new_file_extension}")
                        
            except:
                print(f'Could not convert {m4a_file}')
                logger.error(f'Could not convert {m4a_file}')
                results[file] = ''
        
    return results

def end_script(exit_status=None):
    elapsed_time = time.strftime("%Hh %Mm %Ss", time.gmtime(time.time()))
    flac2mp3_message = f"Info|Completed in {elapsed_time}"
    log(flac2mp3_message)

    if exit_status is not None:
        flac2mp3_exitstatus = exit_status
    log(f"Debug|Exit code {flac2mp3_exitstatus}")
    
    sys.exit(flac2mp3_exitstatus)
                
try:
    #handle testing of the script by lidarr
    if getenv('lidarr_eventtype') is not None:
        if getenv('lidarr_eventtype') == 'Test':
            logger.debug('Lidarr Test event recieved')
            exit(0)
            
        if getenv('lidarr_eventtype') == 'AlbumDownload':
            logger.debug(f'artist.Id: {getenv("lidarr_artist_id")}')
            logger.debug(f'artist.Metadata.Value.Name: {getenv("lidarr_artist_name")}')
            logger.debug(f'artist.Path: {getenv("lidarr_artist_path")}')
            logger.debug(f'artist.Metadata.Value.ForeignArtistId: {getenv("lidarr_artist_mbid")}')
            logger.debug(f'artist.Metadata.Value.Type: {getenv("lidarr_artist_type")}')
            logger.debug(f'album.Id: {getenv("lidarr_album_id")}')
            logger.debug(f'album.Title: {getenv("lidarr_album_title")}')
            logger.debug(f'album.ForeignAlbumId: {getenv("lidarr_album_mbid")}')
            logger.debug(f'release.ForeignReleaseId: {getenv("lidarr_albumrelease_mbid")}')
            logger.debug(f'album.ReleaseDate: {getenv("lidarr_album_releasedate")}')
            logger.debug(f'message.DownloadClient: {getenv("lidarr_download_client")}')
            logger.debug(f'message.DownloadId: {getenv("lidarr_download_id")}')
            logger.debug(f'Pipe separated list of added track paths: {getenv("lidarr_addedtrackpaths")}')
            logger.debug(f'Pipe separated list of deleted files: {getenv("lidarr_deletedpaths")}')


            if getenv('lidarr_addedtrackpaths') is not None:
                logger.debug(f'Track paths: {getenv("lidarr_addedtrackpaths")}')
                trackfile_info = get_trackfile_info(getenv("lidarr_artist_id"),getenv("lidarr_album_id"))
                source_folder = os.path.dirname(getenv('lidarr_addedtrackpaths').split('|')[0])
                logger.debug(f'Album path: {source_folder}')

                process_results = processFiles()
                tracks_to_import = []
                for file in process_results:
                    logger.debug(file)
                    found_object = next((obj for obj in trackfile_info if obj.get("path") == file), None)
                    if process_results[file] is not None and process_results[file] != '':
                        if delete_original_file == True:
                            logger.debug(f"Deleting {file}")
                            delete_track(found_object['id'], file)
                        tracks_to_import.append(process_results[file])
                get_import_info(tracks_to_import, source_folder, getenv("lidarr_download_id"), getenv("lidarr_album_id"))
                exit(0)
    else:
        logger.debug('No triggered by Lidarr')
        exit(1)

except Exception as e:
    logger.error(traceback.format_exc())
    logger.error(f'{e}')
    exit(20)
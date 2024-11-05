#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

VERBOSE = False


def read_markdown_file(filepath):
    """
    Reads the content of a markdown file.

    Args:
        filepath (str): Path to the markdown file.

    Returns:
        str: Content of the markdown file as a string.
    """
    with open(filepath) as file:
        return file.read()


def parse_markdown(markdown_content):
    """
    Parses the content of a markdown file containing film roll information.

    Args:
        markdown_content (str): Content of the markdown file.

    Returns:
        list[dict]: A list of dictionaries, each containing film roll information.
    """
    film_rolls = []
    current_roll = {}
    lines = markdown_content.splitlines()
    count_rolls = sum(1 for line in lines if line.startswith("- Filmstock"))
    if VERBOSE:
        print(f"DEBUG: Found {count_rolls} rolls in input Film Manifest Markdown file")

    for line in lines:
        try:
            if line.strip().startswith("- Filmstock:"):
                if current_roll:
                    film_rolls.append(current_roll)
                    if VERBOSE:
                        print(f"DEBUG: Adding roll {current_roll} to list of film_rolls")
                    current_roll = {}
                current_roll["FilmStock"] = line.split(": ")[1].strip()
            elif "ISO:" in line:
                current_roll["ISO"] = re.search(r"ISO: (\d+)", line).group(1).strip()
            elif "Loaded Date:" in line:
                current_roll["LoadDate"] = (
                    re.search(r"Loaded Date: ([\d/]+)", line).group(1).strip()
                )
            elif "Camera:" in line:
                current_roll["Camera"] = re.search(r"Camera: (.+)", line).group(1).strip()
            elif "Lens:" in line:
                current_roll["Lens"] = re.search(r"Lens: (.+)", line).group(1).strip()
            elif "Shot Location:" in line:
                current_roll["ShotLocation"] = (
                    re.search(r"Shot Location: (.+)", line).group(1).strip()
                )
            elif "Developed Date:" in line:
                current_roll["FilmProcessedDate"] = (
                    re.search(r"Developed Date: ([\d/]+)", line).group(1).strip()
                )
            elif "Developed Location:" in line:
                current_roll["DevelopedBy"] = (
                    re.search(r"Developed Location: (.+)", line).group(1).strip()
                )
            elif "RollNum:" in line:
                current_roll["RollNum"] = re.search(r"RollNum: (\d+)", line).group(1).strip()
        except (AttributeError, IndexError):
            print(f"Error parsing line: {line}")
            continue
    if current_roll:
        film_rolls.append(current_roll)
        if VERBOSE:
            print(f"DEBUG: Adding roll {current_roll} to list of film_rolls")

    # make sure we parsed all the rolls
    if len(film_rolls) != count_rolls:
        print(
            f"Mismatch on number of parsed film_rolls {len(film_rolls)} vs number in Markdown input file {count_rolls}!"
        )
        markdown_rollnums = []
        for line in lines:
            if "RollNum" in line:
                markdown_rollnums.append(line.split(": ")[1].strip())
        film_rolls_rollnums = []
        for roll in film_rolls:
            film_rolls_rollnums.append(roll["RollNum"])
        print("Rolls in Markdown input file but not parsed:")
        print([x for x in markdown_rollnums if x not in film_rolls_rollnums])

    return film_rolls


def apply_exif_data(rolls, image_directory):
    """
    Applies EXIF data to image files in a directory based on film roll information.

    Args:
        rolls (list[dict]): List of dictionaries containing film roll information.
        image_directory (str): Path to the directory with image files.

    Returns:
        None
    """
    tasks = []
    with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        for root, dirs, files in os.walk(image_directory):
            if VERBOSE:
                print(f"DEBUG: Working on dir: {root}")
            for file in files:
                # file naming conventions:
                # 1. `0000XXXX000YY.jpg` where XXXX is a 4-digit RollNum, and YY is a zero-padded PhotoNum (1-36ish)
                # 2. `XXXX_YY.tif` where XXXX is a 4-digit RollNum, and YY is a non-zero-padded PhotoNum (1-36ish)
                if file.lower().endswith((".jpg", ".jpeg", ".tiff", ".tif")):
                    roll_num_match = re.search(r"(\d{8})(\d{4})|(\d{4})_(\d{1,2})", file)
                    if roll_num_match:
                        # handle file naming convention #1
                        if roll_num_match.group(1):
                            roll_num = roll_num_match.group(1).lstrip("0000")
                        # handle file naming convention #2
                        elif roll_num_match.group(3):
                            roll_num = roll_num_match.group(3).strip()
                        else:
                            print(f"ERROR: file naming convention unknown for file {file}")
                            continue

                        # handle file naming convention #1
                        if roll_num_match.group(2):
                            photo_number = int(roll_num_match.group(2))
                        # handle file naming convention #2
                        elif roll_num_match.group(4):
                            photo_number = int(roll_num_match.group(4))
                        else:
                            print(f"ERROR: file naming convention unknown for file {file}")

                        for roll in reversed(rolls):
                            if roll["RollNum"] == roll_num:
                                camera_make, camera_model = roll["Camera"].split(" ", 1)
                                scanner_make, scanner_model = get_original_make_model(
                                    os.path.join(root, file)
                                )
                                date_str = roll["LoadDate"]
                                date_base = datetime.strptime(date_str, "%m/%d/%y")
                                date = (
                                    date_base.strftime("%Y:%m:%d %H:")
                                    + f"{photo_number:02}"
                                    + ":00"
                                )
                                exiftool_cmd = [
                                    "exiftool",
                                    "-q",
                                    "-q",
                                    "-m",
                                    "-overwrite_original",
                                    f"-Make={camera_make}",
                                    f"-Model={camera_model}",
                                    f'-Lens={roll["Lens"]}',
                                    f'-Location={roll["ShotLocation"]}',
                                    f'-XMP-AnalogueData:FilmStock={roll["FilmStock"]}',
                                    "-XMP-AnalogueData:FilmFormat=35mm",
                                    "-XMP-AnalogueData:FilmDeveloper=Unknown",
                                    f'-XMP-AnalogueData:FilmProcessLab={roll["DevelopedBy"]}',
                                    f"-XMP-AnalogueData:FilmScanner={scanner_make} {scanner_model}",
                                    f'-XMP-AnalogueData:FilmProcessedDate={roll["FilmProcessedDate"]}',
                                    f'-XMP-AnalogueData:RollNum={roll["RollNum"]}',
                                    f'-ISO={roll["ISO"]}',
                                    f"-DateTimeOriginal={date}",
                                    os.path.join(root, file),
                                ]
                                exif_file = os.path.join(root, "exif.txt")
                                if VERBOSE:
                                    print(
                                        f"DEBUG: generated exiftool command {exiftool_cmd} for roll {roll['RollNum']}"
                                        f"DEBUG: creating exif.txt file at {exif_file}"
                                    )
                                tasks.append(executor.submit(run_exiftool_cmd, exiftool_cmd))
                                tasks.append(executor.submit(write_exif_file, roll, exif_file))
                                break
        for future in as_completed(tasks):
            try:
                future.result()
            except Exception as e:
                print(f"Exception when gathering results of future {future}: {e}")


def run_exiftool_cmd(cmd):
    """
    Runs a given exiftool command using the subprocess module.

    Args:
        cmd (list): The exiftool command to run.

    Returns:
        None
    """
    subprocess.run(cmd)


def get_original_make_model(filepath):
    """
    Retrieves the original scanner make and model of an image file using exiftool.

    Args:
        filepath (str): Path to the image file.

    Returns:
        tuple: A tuple containing the make and model of the scanner.
    """
    try:
        result = subprocess.run(
            ["exiftool", "-s", "-s", "-s", "-Make", "-Model", filepath],
            capture_output=True,
            text=True,
        )
        make = result.stdout.split("\n")[0].strip()
        model = result.stdout.split("\n")[1].strip()
        if VERBOSE:
            print(f"Found scanner make {make} and model {model}")
    except UnboundLocalError:
        print(f"Unable to find scanner make and model on image {filepath}. Setting to 'Unknown'")
        make = "Unknown Make"
        model = "Unknown Model"
    return (make, model)


def write_exif_file(film_roll, filepath):
    """
    Writes gathered EXIF data to a text file in the roll directory

    Args:
        film_roll (dict): dictionary containing film roll information.
        filepath (str): Path to the file to write exif.txt.

    Returns:
        None
    """
    with open(filepath, "w") as file:
        file.write(f"Camera={film_roll['Camera']}\n")
        file.write(f"Lens={film_roll['Lens']}\n")
        file.write(f"Film={film_roll['FilmStock']}\n")
        file.write(f"ISO={film_roll['ISO']}\n")
        file.write(f"MajorityShotDate={film_roll['LoadDate']}\n")
        file.write(f"ShotLocation={film_roll['ShotLocation']}\n")
        file.write(f"Developed={film_roll['DevelopedBy']}\n")
        file.write(f"DevelopedDate={film_roll['FilmProcessedDate']}\n")
        file.flush()


def is_markdown_file(filepath):
    """
    Checks if the given file is a markdown file by its extension and content.

    Args:
        filepath (str): Path to the file to check.

    Returns:
        bool: True if the file is a markdown file, False otherwise.
    """
    if not filepath.lower().endswith(".md"):
        return False
    with open(filepath) as file:
        first_line = file.readline().strip()
        return first_line.startswith("#") or first_line.startswith("-")


def main():
    """
    Main function to read markdown file, parse film roll information, and apply EXIF data to image files.

    Args:
        None

    Returns:
        None
    """
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--film-manifest", type=str, help="Path to film manifest Markdown file", required=True
    )
    parser.add_argument("--images-dir", type=str, help="Path to images directory", required=True)
    parser.add_argument(
        "-v", "--verbose", help="Increase logging verbosity", required=False, action="store_true"
    )
    args = parser.parse_args()

    # Ensure parsed arguments are valid
    markdown_filepath = args.film_manifest  # Path to the markdown manifest file
    if not is_markdown_file(markdown_filepath):
        print(
            "Film manifest file is not a Markdown file, are you sure you entered the correct path? Exiting..."
        )
        sys.exit(1)
    images_directory = args.images_dir  # Path to the directory with image files
    if not os.path.isdir(images_directory):
        print(
            "Images directory is not a directory, are you sure you entered the correct path? Exiting..."
        )
        sys.exit(2)
    global VERBOSE
    VERBOSE = args.verbose or False
    print(
        f"Running EXIFizer on images directory {images_directory} with film manifest {markdown_filepath}"
    )

    # Run the program with validated arguments
    markdown_content = read_markdown_file(markdown_filepath)
    film_rolls = parse_markdown(markdown_content)
    apply_exif_data(film_rolls, images_directory)


if __name__ == "__main__":
    main()

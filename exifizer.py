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
    try:
        with open(filepath, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        print(f"Error reading markdown file {filepath}: {e}")
        sys.exit(1)


def safe_regex_extract(pattern, text, default="None"):
    """
    Safely extract text using regex with a default fallback.

    Args:
        pattern (str): Regex pattern to match.
        text (str): Text to search in.
        default (str): Default value if no match found.

    Returns:
        str: Extracted text or default value.
    """
    try:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else default
    except (AttributeError, IndexError):
        return default


def parse_date_with_fallback(date_str, field_name="date"):
    """
    Parse a date string with multiple format attempts and error handling.

    Args:
        date_str (str): Date string to parse.
        field_name (str): Name of the field for error reporting.

    Returns:
        str: Formatted date string or "Unknown" if parsing fails.
    """
    if not date_str or date_str.strip() in ["", "None", "Unknown"]:
        return "Unknown"

    date_formats = ["%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%y", "%d/%m/%Y"]

    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str.strip(), fmt)
            return parsed_date.strftime("%m/%d/%y")
        except ValueError:
            continue

    print(f"Warning: Could not parse {field_name} '{date_str}', using 'Unknown'")
    return "Unknown"


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

    for line_num, line in enumerate(lines, 1):
        try:
            if line.strip().startswith("- Filmstock:"):
                if current_roll:
                    # Validate and set defaults for required fields before adding
                    current_roll = validate_and_set_defaults(current_roll)
                    film_rolls.append(current_roll)
                    if VERBOSE:
                        print(
                            f"DEBUG: Adding roll {current_roll.get('RollNum', 'Unknown')} to list of film_rolls"
                        )
                    current_roll = {}
                current_roll["FilmStock"] = safe_regex_extract(r": (.+)", line)

            elif "ISO:" in line:
                iso_value = safe_regex_extract(r"ISO: (\d+)", line, "100")
                try:
                    # Validate ISO is a number
                    int(iso_value)
                    current_roll["ISO"] = iso_value
                except ValueError:
                    print(
                        f"Warning: Invalid ISO value '{iso_value}' on line {line_num}, using '100'"
                    )
                    current_roll["ISO"] = "100"

            elif "Loaded Date:" in line:
                date_str = safe_regex_extract(r"Loaded Date: ([\d/\-]+)", line)
                current_roll["LoadDate"] = parse_date_with_fallback(date_str, "LoadDate")

            elif "Camera:" in line:
                current_roll["Camera"] = safe_regex_extract(r"Camera: (.+)", line)

            elif "Lens:" in line:
                current_roll["Lens"] = safe_regex_extract(r"Lens: (.+)", line)

            elif "Filter:" in line:
                current_roll["Filter"] = safe_regex_extract(r"Filter: (.+)", line)

            elif "Notes:" in line:
                current_roll["Notes"] = safe_regex_extract(r"Notes: (.+)", line)

            elif "Subject:" in line:
                current_roll["Subject"] = safe_regex_extract(r"Subject: (.+)", line)

            elif "Shot Location:" in line:
                current_roll["ShotLocation"] = safe_regex_extract(r"Shot Location: (.+)", line)

            elif "Developed Date:" in line:
                date_str = safe_regex_extract(r"Developed Date: ([\d/\-]+)", line)
                current_roll["FilmProcessedDate"] = parse_date_with_fallback(
                    date_str, "FilmProcessedDate"
                )

            elif "Developed Location:" in line:
                current_roll["DevelopedBy"] = safe_regex_extract(r"Developed Location: (.+)", line)

            elif "RollNum:" in line:
                roll_num = safe_regex_extract(r"RollNum: (\d+)", line, "0000")
                try:
                    # Validate and format roll number
                    int(roll_num)
                    current_roll["RollNum"] = roll_num.zfill(4)
                except ValueError:
                    print(f"Warning: Invalid RollNum '{roll_num}' on line {line_num}, using '0000'")
                    current_roll["RollNum"] = "0000"

        except Exception as e:
            print(f"Error parsing line {line_num}: '{line}' - {e}")
            continue

    # Handle the last roll
    if current_roll:
        current_roll = validate_and_set_defaults(current_roll)
        film_rolls.append(current_roll)
        if VERBOSE:
            print(
                f"DEBUG: Adding final roll {current_roll.get('RollNum', 'Unknown')} to list of film_rolls"
            )

    # Verify we parsed all the rolls
    if len(film_rolls) != count_rolls:
        print(
            f"Warning: Mismatch on number of parsed film_rolls {len(film_rolls)} vs number in Markdown input file {count_rolls}!"
        )
        markdown_rollnums = []
        for line in lines:
            if "RollNum" in line:
                roll_num = safe_regex_extract(r"RollNum: (\d+)", line, "Unknown")
                markdown_rollnums.append(roll_num.zfill(4) if roll_num.isdigit() else roll_num)

        film_rolls_rollnums = [roll.get("RollNum", "Unknown") for roll in film_rolls]
        missing_rolls = [x for x in markdown_rollnums if x not in film_rolls_rollnums]
        if missing_rolls:
            print("Rolls in Markdown input file but not parsed:")
            print(missing_rolls)

    return film_rolls


def validate_and_set_defaults(roll):
    """
    Validate and set default values for a film roll dictionary.

    Args:
        roll (dict): Film roll dictionary to validate.

    Returns:
        dict: Validated roll with defaults set.
    """
    defaults = {
        "FilmStock": "Unknown Film",
        "ISO": "100",
        "LoadDate": "Unknown",
        "Camera": "Unknown Camera",
        "Lens": "Unknown Lens",
        "Filter": "None",
        "Notes": "None",
        "Subject": "None",
        "ShotLocation": "Unknown Location",
        "FilmProcessedDate": "Unknown",
        "DevelopedBy": "Unknown Lab",
        "RollNum": "0000",
    }

    for key, default_value in defaults.items():
        if key not in roll or not roll[key] or roll[key].strip() == "":
            roll[key] = default_value
            if VERBOSE:
                print(f"DEBUG: Set default value '{default_value}' for missing field '{key}'")

    return roll


def remove_thm_files(image_directory):
    """
    Removes .thm files from image directory

    Args:
        image_directory (str): Path to the directory with image files.

    Returns:
        None
    """
    removed_count = 0
    for root, dirs, files in os.walk(image_directory):
        for filename in files:
            if filename.lower().endswith(".thm"):
                file_path = os.path.join(root, filename)
                try:
                    os.remove(file_path)
                    removed_count += 1
                    if VERBOSE:
                        print(f"Removed: {file_path}")
                except OSError as e:
                    print(f"Error removing {file_path}: {e}")

    if removed_count > 0:
        print(f"Removed {removed_count} .thm files")


def generate_photo_datetime(load_date_str, photo_number):
    """
    Generate a datetime string for a photo based on load date and photo number.

    Args:
        load_date_str (str): Load date string.
        photo_number (int): Photo number on the roll.

    Returns:
        str: Formatted datetime string for EXIF.
    """
    try:
        if load_date_str == "Unknown":
            # Use a default date if load date is unknown
            return f"1900:01:01 {photo_number:02}:00:00"

        date_base = datetime.strptime(load_date_str, "%m/%d/%y")
        return f"{date_base.strftime('%Y:%m:%d')} {photo_number:02}:00:00"
    except ValueError as e:
        print(f"Error generating datetime for load date '{load_date_str}': {e}")
        return f"1900:01:01 {photo_number:02}:00:00"


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
    processed_files = 0

    with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        for root, dirs, files in os.walk(image_directory):
            if VERBOSE:
                print(f"DEBUG: Working on dir: {root}")
            for file in files:
                if VERBOSE:
                    print(f"DEBUG: Working on file: {file}")
                # file naming conventions:
                # 1. `0000XXXX000YY.jpg` where XXXX is a 4-digit RollNum, and YY is a zero-padded PhotoNum (1-36ish)
                # 2. `XXXX_YY.tif` where XXXX is a 4-digit RollNum, and YY is a non-zero-padded PhotoNum (1-36ish)
                if file.lower().endswith((".jpg", ".jpeg", ".tiff", ".tif")):
                    roll_num_match = re.search(r"(\d{8})(\d{4})|(\d{4})_(\d{1,2})", file)
                    if not roll_num_match:
                        print(f"Warning: Could not parse roll number from filename: {file}")
                        continue

                    try:
                        # handle file naming convention #1
                        if roll_num_match.group(1):
                            roll_num = roll_num_match.group(1).lstrip("0000").zfill(4)
                            photo_number = (
                                int(roll_num_match.group(2)) if roll_num_match.group(2) else 1
                            )
                        # handle file naming convention #2
                        elif roll_num_match.group(3):
                            roll_num = roll_num_match.group(3).strip().zfill(4)
                            photo_number = (
                                int(roll_num_match.group(4)) if roll_num_match.group(4) else 1
                            )
                        else:
                            print(f"Warning: Unknown file naming convention for file {file}")
                            continue

                        if VERBOSE:
                            print(
                                f"DEBUG: file {file} assigned roll_num {roll_num} and photo_number {photo_number}"
                            )

                        # Find matching roll
                        matching_roll = None
                        for roll in reversed(rolls):
                            if VERBOSE:
                                print(
                                    f"DEBUG: Comparing roll {roll['RollNum']} with file roll_num {roll_num}"
                                )
                            if roll["RollNum"] == roll_num:
                                matching_roll = roll
                                break

                        if not matching_roll:
                            print(
                                f"Warning: No matching roll found for file {file} (roll {roll_num})"
                            )
                            continue

                        # Parse camera make and model safely
                        try:
                            camera_parts = matching_roll["Camera"].split(" ", 1)
                            camera_make = camera_parts[0] if len(camera_parts) > 0 else "Unknown"
                            camera_model = camera_parts[1] if len(camera_parts) > 1 else "Camera"
                        except (AttributeError, IndexError):
                            camera_make, camera_model = "Unknown", "Camera"

                        # Get scanner info
                        scanner_make, scanner_model = get_original_make_model(
                            os.path.join(root, file)
                        )

                        # Generate datetime
                        date = generate_photo_datetime(matching_roll["LoadDate"], photo_number)

                        # Build comprehensive EXIF command with fields that show up in Google Photos
                        file_path = os.path.join(root, file)
                        exiftool_cmd = [
                            "exiftool",
                            "-q",
                            "-q",
                            "-m",
                            "-overwrite_original",
                            # Basic camera info (shows in Google Photos)
                            f"-Make={camera_make}",
                            f"-Model={camera_model}",
                            f"-LensModel={matching_roll['Lens']}",
                            f"-ISO={matching_roll['ISO']}",
                            f"-DateTimeOriginal={date}",
                            # Location (shows in Google Photos)
                            f"-Location={matching_roll['ShotLocation']}",
                            f"-LocationCreated={matching_roll['ShotLocation']}",
                            f"-City={matching_roll['ShotLocation']}",
                            # Subject and description (shows in Google Photos)
                            f"-Subject={matching_roll['Subject']}",
                            f"-Description={matching_roll['Notes']}",
                            f"-ImageDescription={matching_roll['Notes']}",
                            f"-Caption-Abstract={matching_roll['Notes']}",
                            # Keywords for better organization (shows in Google Photos)
                            "-Keywords=Film Photography",
                            f"-Keywords={matching_roll['FilmStock']}",
                            f"-Keywords={camera_make} {camera_model}",
                            f"-Keywords=Roll {matching_roll['RollNum']}",
                            # Copyright and creator info (shows in Google Photos)
                            "-Artist=Film Photographer",
                            "-Copyright=© Film Photography Collection",
                            # Film-specific metadata in XMP namespace
                            f"-XMP-AnalogueData:Filter={matching_roll['Filter']}",
                            f"-XMP-AnalogueData:FilmStock={matching_roll['FilmStock']}",
                            "-XMP-AnalogueData:FilmFormat=35mm",
                            "-XMP-AnalogueData:FilmDeveloper=Unknown",
                            f"-XMP-AnalogueData:FilmProcessLab={matching_roll['DevelopedBy']}",
                            f"-XMP-AnalogueData:FilmScanner={scanner_make} {scanner_model}",
                            f"-XMP-AnalogueData:FilmProcessedDate={matching_roll['FilmProcessedDate']}",
                            f"-XMP-AnalogueData:RollNum={matching_roll['RollNum']}",
                            f"-XMP-AnalogueData:PhotoNumber={photo_number}",
                            f"-XMP-AnalogueData:Subject={matching_roll['Subject']}",
                            f"-XMP-AnalogueData:Notes={matching_roll['Notes']}",
                            # Additional fields that may show up in various viewers
                            f"-UserComment=Film: {matching_roll['FilmStock']}, ISO {matching_roll['ISO']}, {matching_roll['Lens']}",
                            f"-SpecialInstructions=Developed at {matching_roll['DevelopedBy']} on {matching_roll['FilmProcessedDate']}",
                            file_path,
                        ]

                        exif_file = os.path.join(root, "exif.txt")
                        if VERBOSE:
                            print(
                                f"DEBUG: Generated exiftool command for roll {matching_roll['RollNum']}"
                            )
                            print(f"DEBUG: Creating exif.txt file at {exif_file}")

                        tasks.append(executor.submit(run_exiftool_cmd, exiftool_cmd, file))
                        tasks.append(executor.submit(write_exif_file, matching_roll, exif_file))
                        processed_files += 1

                    except (ValueError, IndexError, KeyError) as e:
                        print(f"Error processing file {file}: {e}")
                        continue

        # Wait for all tasks to complete and handle exceptions
        failed_tasks = 0
        for future in as_completed(tasks):
            try:
                future.result()
            except Exception as e:
                print(f"Exception when processing task: {e}")
                failed_tasks += 1

    print(f"Processed {processed_files} image files")
    if failed_tasks > 0:
        print(f"Warning: {failed_tasks} tasks failed during processing")


def run_exiftool_cmd(cmd, filename="unknown"):
    """
    Runs a given exiftool command using the subprocess module.

    Args:
        cmd (list): The exiftool command to run.
        filename (str): Filename for error reporting.

    Returns:
        None
    """
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0 and VERBOSE:
            print(f"Warning: exiftool returned non-zero exit code for {filename}: {result.stderr}")
    except Exception as e:
        print(f"Error running exiftool for {filename}: {e}")


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
            check=False,
            timeout=10,  # Add timeout to prevent hanging
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            make = lines[0].strip() if len(lines) > 0 and lines[0].strip() else "Unknown Make"
            model = lines[1].strip() if len(lines) > 1 and lines[1].strip() else "Unknown Model"

            if VERBOSE:
                print(f"Found scanner make '{make}' and model '{model}' for {filepath}")
            return (make, model)
        else:
            if VERBOSE:
                print(f"exiftool failed for {filepath}: {result.stderr}")

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        if VERBOSE:
            print(f"Error getting scanner info for {filepath}: {e}")

    print(f"Unable to find scanner make and model on image {filepath}. Setting to 'Unknown'")
    return ("Unknown Make", "Unknown Model")


def write_exif_file(film_roll, filepath):
    """
    Writes gathered EXIF data to a text file in the roll directory

    Args:
        film_roll (dict): dictionary containing film roll information.
        filepath (str): Path to the file to write exif.txt.

    Returns:
        None
    """
    try:
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(f"Camera={film_roll['Camera']}\n")
            file.write(f"Lens={film_roll['Lens']}\n")
            file.write(f"Filter={film_roll['Filter']}\n")
            file.write(f"Film={film_roll['FilmStock']}\n")
            file.write(f"ISO={film_roll['ISO']}\n")
            file.write(f"MajorityShotDate={film_roll['LoadDate']}\n")
            file.write(f"Subject={film_roll['Subject']}\n")
            file.write(f"ShotLocation={film_roll['ShotLocation']}\n")
            file.write(f"Developed={film_roll['DevelopedBy']}\n")
            file.write(f"DevelopedDate={film_roll['FilmProcessedDate']}\n")
            file.write(f"Notes={film_roll['Notes']}\n")
            file.flush()
    except OSError as e:
        print(f"Error writing exif file {filepath}: {e}")


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
    try:
        with open(filepath, encoding="utf-8") as file:
            first_line = file.readline().strip()
            return first_line.startswith("#") or first_line.startswith("-")
    except OSError:
        return False


def main():
    """
    Main function to read markdown file, parse film roll information, and apply EXIF data to image files.

    Args:
        None

    Returns:
        None
    """
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Apply EXIF data to film photography images based on a markdown manifest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  %(prog)s --film-manifest rolls.md --images-dir /path/to/images --verbose

The markdown manifest should contain film roll information with the following supported fields:
  - Filmstock: [required] Name of the film stock
  - ISO: [optional] ISO value (default: 100)
  - Loaded Date: [optional] Date film was loaded (default: Unknown)
  - Camera: [optional] Camera make and model (default: Unknown Camera)
  - Lens: [optional] Lens information (default: Unknown Lens)
  - Filter: [optional] Filter used (default: None)
  - Notes: [optional] Additional notes (default: None)
  - Subject: [optional] Subject of the photos (default: None)
  - Shot Location: [optional] Location where photos were taken (default: Unknown Location)
  - Developed Date: [optional] Date film was developed (default: Unknown)
  - Developed Location: [optional] Lab that developed the film (default: Unknown Lab)
  - RollNum: [required] Roll number for matching with image files
        """,
    )
    parser.add_argument(
        "--film-manifest",
        type=str,
        help="Path to film manifest Markdown file",
        required=True,
    )
    parser.add_argument("--images-dir", type=str, help="Path to images directory", required=True)
    parser.add_argument(
        "-v",
        "--verbose",
        help="Increase logging verbosity",
        required=False,
        action="store_true",
    )
    args = parser.parse_args()

    # Ensure parsed arguments are valid
    markdown_filepath = args.film_manifest  # Path to the markdown manifest file
    if not os.path.exists(markdown_filepath):
        print(f"Film manifest file '{markdown_filepath}' does not exist. Exiting...")
        sys.exit(1)
    if not is_markdown_file(markdown_filepath):
        print(
            "Film manifest file is not a Markdown file, are you sure you entered the correct path? Exiting..."
        )
        sys.exit(1)
    images_directory = args.images_dir  # Path to the directory with image files
    if not os.path.exists(images_directory):
        print(f"Images directory '{images_directory}' does not exist. Exiting...")
        sys.exit(2)
    if not os.path.isdir(images_directory):
        print(
            "Images directory is not a directory, are you sure you entered the correct path? Exiting..."
        )
        sys.exit(2)
    global VERBOSE
    VERBOSE = args.verbose or False

    print(
        f"Running EXIFizer on images directory '{images_directory}' with film manifest '{markdown_filepath}'"
    )

    try:
        # Run the program with validated arguments
        markdown_content = read_markdown_file(markdown_filepath)
        film_rolls = parse_markdown(markdown_content)

        if not film_rolls:
            print("No film rolls found in the manifest file. Exiting...")
            sys.exit(3)

        print(f"Successfully parsed {len(film_rolls)} film rolls from manifest")
        remove_thm_files(images_directory)
        apply_exif_data(film_rolls, images_directory)
        print("EXIFizer processing completed successfully!")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error during processing: {e}")
        if VERBOSE:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

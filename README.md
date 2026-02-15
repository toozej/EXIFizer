# EXIFizer

A bulk EXIF data tagging tool for analog / film photography.

## Pre-Reqs
1. Install Python 3.11 or higher

2. Install EXIFTool (and curl for downloading EXIFizer)
   https://exiftool.org/
   ```
   brew install exiftool curl || sudo dnf install -y perl-Image-ExifTool curl || sudo apt-get install -y libimage-exiftool-perl curl
   ```

3. Ensure you have a `~/.ExifTool_config` file
   ```
   curl -sLo ~/.ExifTool_config https://raw.githubusercontent.com/toozej/EXIFizer/main/.ExifTool_config
   ```

## Installation

### Option 1: Using uv (recommended)
1. Install uv: https://docs.astral.sh/uv/getting-started/installation/

2. Clone the repository and install:
   ```
   git clone https://github.com/toozej/EXIFizer.git
   cd EXIFizer
   uv sync
   ```

### Option 2: Direct script usage (no installation required)
```
curl -sLo ~/bin/exifizer https://raw.githubusercontent.com/toozej/EXIFizer/main/exifizer.py
chmod +x ~/bin/exifizer
```

## Usage
1. Put a file `film_manifest.md` in a known location. See `example_input_film_manifest.md` for an example

2. Organize your images directories in one of two ways:
   - Directory name: `0000XXXX/` where XXXX is a 4-digit RollNum
     Image name: `0000XXXX000YY.jpg` where XXXX is a 4-digit RollNum, and YY is a zero-padded PhotoNum (1-36ish)
   - Directory name: `roll_XXXX` where XXXX is a 4-digit RollNum
     Image name: `XXXX_YY.tif` where XXXX is a 4-digit RollNum, and YY is a non-zero-padded PhotoNum (1-36ish)

3. Run EXIFizer against a directory of images with a film manifest file:

   **Using uv:**
   ```
   uv run exifizer --film-manifest path/to/film_manifest.md --images-dir path/to/dir/of/images/
   ```

   **Using direct script:**
   ```
   python3 exifizer.py --film-manifest path/to/film_manifest.md --images-dir path/to/dir/of/images/
   ```

## Development
Run checks and tests locally:
```
make local-run
```

Or manually:
```
uv sync --all-groups
make pre-commit
uv run pytest
```

## Inspiration / Credits
- https://exiftool.org/faq.html
- https://github.com/thetestspecimen/film-exif/
- https://github.com/toozej/python-starter
- https://github.com/toozej/tools
- ChatGPT and Kilocode :)

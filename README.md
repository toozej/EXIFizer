# EXIFizer

A bulk EXIF data tagging tool for analog / film photography.

## Pre-Reqs
1. Install Python 3.12 or higher (may work with older versions, but not tested)

2. Install EXIFTool (and curl for downloading EXIFizer)
https://exiftool.org/
```
brew install exiftool curl || sudo dnf install -y perl-Image-ExifTool curl || sudo apt-get install -y libimage-exiftool-perl curl
```

3. Ensure you have a `~/.ExifTool_config` file
```
curl -sLo ~/.ExifTool_config https://raw.githubusercontent.com/toozej/EXIFizer/main/.ExifTool_config
```

4. Grab a copy of EXIFizer to your $bin directory
```
curl -sLo ~/bin/exifizer https://raw.githubusercontent.com/toozej/EXIFizer/main/exifizer.py
```

## Usage
1. Put a file `film_manifest.md` in a known location. See `example_input_film_manifest.md` for an example

2. Organize your images directories in one of two ways:
   - Directory name: `0000XXXX/` where XXXX is a 4-digit RollNum
     Image name: `0000XXXX000YY.jpg` where XXXX is a 4-digit RollNum, and YY is a zero-padded PhotoNum (1-36ish)
   - Directory name: `roll_XXXX` where XXXX is a 4-digit RollNum
     Image name: `XXXX_YY.tif` where XXXX is a 4-digit RollNum, and YY is a non-zero-padded PhotoNum (1-36ish)

3. Run EXIFizer against a directory of images with a film manifest file
```
exifizer --film-manifest path/to/film_manifest.md --images-dir path/to/dir/of/images/
```

## Inspiration / Credits
- https://exiftool.org/faq.html
- https://github.com/thetestspecimen/film-exif/
- ChatGPT :D

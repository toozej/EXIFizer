# EXIFizer

A bulk EXIF data tagging tool for analog / film photography.

## Pre-reqs
1. Install EXIFTool (and curl for downloading EXIFizer)
https://exiftool.org/
```
sudo dnf install -y perl-Image-ExifTool curl
```

2. Ensure you have a `~/.ExifTool_config` file
```
curl -sLo ~/.ExifTool_config https://raw.githubusercontent.com/toozej/EXIFizer/main/.ExifTool_config
```

3. Grab a copy of EXIFizer to your $bin directory
```
curl -sLo ~/bin/exifizer https://raw.githubusercontent.com/toozej/EXIFizer/main/exifizer
```

4. Put your scanned photos in numerically named directories (like "00004423")

## Usage
1. Put a file `exif.txt` like the following in each directory of scanned photos
```
Camera=Nikon N80
Lens=50mm f/1.8
Location=Somewhere, ST
Film=Ilford HP5+
ISO=1600
Exposures=36
MajorityShotDate=2023/09/12
Developed=Some Lab, Somewhere, ST
DevelopedDate=2023/10/12
```

2. Run EXIFizer against a directory of scanned photos
```
exifizer path/to/dir/of/scanned/photos/$rollnum
```

3. MEGA EXIFizer (Run EXIFizer against a whole bunch of directories)
```
find path/to/base/dir/of/scanned/photos -type d -exec exifizer {} \;
```

## Inspiration / Credits
- https://exiftool.org/faq.html
- https://github.com/thetestspecimen/film-exif/
- ChatGPT :D

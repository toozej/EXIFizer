# EXIFizer

A bulk EXIF data tagging tool for analog / film photography.

## Usage
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

4. Run EXIFizer against a local directory of scanned photos
```
exifizer path/to/dir/of/scanned/photos
```

## Inspiration / Credits
- https://exiftool.org/faq.html
- https://github.com/thetestspecimen/film-exif/
- ChatGPT :D

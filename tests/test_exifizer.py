from unittest.mock import patch

import pytest

import exifizer


class TestReadMarkdownFile:
    def test_read_valid_file(self, tmp_path):
        content = "# Test Markdown\n- Filmstock: Kodak Portra 400"
        filepath = tmp_path / "test.md"
        filepath.write_text(content)
        result = exifizer.read_markdown_file(str(filepath))
        assert result == content

    def test_read_nonexistent_file(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            exifizer.read_markdown_file("/nonexistent/path/file.md")
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error reading markdown file" in captured.out

    def test_read_file_with_encoding(self, tmp_path):
        content = "# Test\n- Filmstock: Fujifilm"
        filepath = tmp_path / "test.md"
        filepath.write_text(content, encoding="utf-8")
        result = exifizer.read_markdown_file(str(filepath))
        assert result == content


class TestSafeRegexExtract:
    def test_extract_match(self):
        text = "Filmstock: Kodak Portra 400"
        result = exifizer.safe_regex_extract(r": (.+)", text)
        assert result == "Kodak Portra 400"

    def test_extract_no_match_returns_default(self):
        text = "No colon here"
        result = exifizer.safe_regex_extract(r": (.+)", text)
        assert result == "None"

    def test_extract_custom_default(self):
        text = "No match"
        result = exifizer.safe_regex_extract(r"ISO: (\d+)", text, "100")
        assert result == "100"

    def test_extract_numeric_value(self):
        text = "ISO: 400"
        result = exifizer.safe_regex_extract(r"ISO: (\d+)", text)
        assert result == "400"


class TestParseDateWithFallback:
    def test_parse_mm_dd_yy_format(self):
        result = exifizer.parse_date_with_fallback("01/15/24", "test")
        assert result == "01/15/24"

    def test_parse_mm_dd_yyyy_format(self):
        result = exifizer.parse_date_with_fallback("01/15/2024", "test")
        assert result == "01/15/24"

    def test_parse_yyyy_mm_dd_format(self):
        result = exifizer.parse_date_with_fallback("2024-01-15", "test")
        assert result == "01/15/24"

    def test_parse_dd_mm_yy_format(self):
        result = exifizer.parse_date_with_fallback("15/01/24", "test")
        assert result == "01/15/24"

    def test_parse_invalid_date_returns_unknown(self, capsys):
        result = exifizer.parse_date_with_fallback("invalid-date", "test")
        assert result == "Unknown"
        captured = capsys.readouterr()
        assert "Warning" in captured.out

    def test_parse_empty_string_returns_unknown(self):
        result = exifizer.parse_date_with_fallback("", "test")
        assert result == "Unknown"

    def test_parse_none_string_returns_unknown(self):
        result = exifizer.parse_date_with_fallback("None", "test")
        assert result == "Unknown"

    def test_parse_unknown_string_returns_unknown(self):
        result = exifizer.parse_date_with_fallback("Unknown", "test")
        assert result == "Unknown"


class TestValidateAndSetDefaults:
    def test_valid_roll_no_changes(self):
        roll = {
            "FilmStock": "Kodak Portra 400",
            "ISO": "400",
            "LoadDate": "01/15/24",
            "Camera": "Canon AE-1",
            "Lens": "50mm f/1.4",
            "Filter": "None",
            "Notes": "Test notes",
            "Subject": "Portrait",
            "ShotLocation": "New York",
            "FilmProcessedDate": "01/20/24",
            "DevelopedBy": "Local Lab",
            "RollNum": "0001",
        }
        result = exifizer.validate_and_set_defaults(roll)
        assert result == roll

    def test_empty_roll_gets_defaults(self):
        roll = {}
        result = exifizer.validate_and_set_defaults(roll)
        assert result["FilmStock"] == "Unknown Film"
        assert result["ISO"] == "100"
        assert result["LoadDate"] == "Unknown"
        assert result["Camera"] == "Unknown Camera"
        assert result["Lens"] == "Unknown Lens"
        assert result["Filter"] == "None"
        assert result["Notes"] == "None"
        assert result["Subject"] == "None"
        assert result["ShotLocation"] == "Unknown Location"
        assert result["FilmProcessedDate"] == "Unknown"
        assert result["DevelopedBy"] == "Unknown Lab"
        assert result["RollNum"] == "0000"

    def test_partial_roll_gets_missing_defaults(self):
        roll = {"FilmStock": "Kodak Portra 400", "ISO": "400"}
        result = exifizer.validate_and_set_defaults(roll)
        assert result["FilmStock"] == "Kodak Portra 400"
        assert result["ISO"] == "400"
        assert result["LoadDate"] == "Unknown"
        assert result["Camera"] == "Unknown Camera"

    def test_empty_values_get_defaults(self):
        roll = {"FilmStock": "", "ISO": "   "}
        result = exifizer.validate_and_set_defaults(roll)
        assert result["FilmStock"] == "Unknown Film"
        assert result["ISO"] == "100"


class TestParseMarkdown:
    def test_parse_single_roll(self):
        content = """# Film Roll
- Filmstock: Kodak Portra 400
- ISO: 400
- Loaded Date: 01/15/24
- Camera: Canon AE-1
- Lens: 50mm f/1.4
- Filter: None
- Notes: Test roll
- Subject: Portrait
- Shot Location: New York
- Developed Date: 01/20/24
- Developed Location: Local Lab
- RollNum: 0001
"""
        result = exifizer.parse_markdown(content)
        assert len(result) == 1
        assert result[0]["FilmStock"] == "Kodak Portra 400"
        assert result[0]["ISO"] == "400"
        assert result[0]["LoadDate"] == "01/15/24"
        assert result[0]["Camera"] == "Canon AE-1"
        assert result[0]["Lens"] == "50mm f/1.4"
        assert result[0]["FocalLength"] == "50"
        assert result[0]["RollNum"] == "0001"

    def test_parse_multiple_rolls(self):
        content = """# Film Rolls
- Filmstock: Kodak Portra 400
- ISO: 400
- RollNum: 0001

- Filmstock: Fujifilm Superia
- ISO: 200
- RollNum: 0002
"""
        result = exifizer.parse_markdown(content)
        assert len(result) == 2
        assert result[0]["FilmStock"] == "Kodak Portra 400"
        assert result[1]["FilmStock"] == "Fujifilm Superia"

    def test_parse_extract_focal_length(self):
        content = """- Filmstock: Test Film
- Lens: 35mm f/2.8
- RollNum: 0001
"""
        result = exifizer.parse_markdown(content)
        assert result[0]["FocalLength"] == "35"

    def test_parse_focal_length_no_match(self):
        content = """- Filmstock: Test Film
- Lens: Unknown Lens
- RollNum: 0001
"""
        result = exifizer.parse_markdown(content)
        assert result[0]["FocalLength"] == "Unknown"

    def test_parse_invalid_iso_uses_default(self):
        content = """- Filmstock: Test Film
- ISO: invalid
- RollNum: 0001
"""
        result = exifizer.parse_markdown(content)
        assert result[0]["ISO"] == "100"

    def test_parse_invalid_rollnum_uses_default(self):
        content = """- Filmstock: Test Film
- RollNum: invalid
"""
        result = exifizer.parse_markdown(content)
        assert result[0]["RollNum"] == "0000"

    def test_parse_rollnum_padding(self):
        content = """- Filmstock: Test Film
- RollNum: 5
"""
        result = exifizer.parse_markdown(content)
        assert result[0]["RollNum"] == "0005"


class TestGeneratePhotoDatetime:
    def test_generate_datetime_valid_date(self):
        result = exifizer.generate_photo_datetime("01/15/24", 5)
        assert result == "2024:01:15 00:05:00"

    def test_generate_datetime_unknown_date(self):
        result = exifizer.generate_photo_datetime("Unknown", 10)
        assert result == "1900:01:01 00:10:00"

    def test_generate_datetime_photo_number_padding(self):
        result = exifizer.generate_photo_datetime("01/15/24", 3)
        assert "00:03:00" in result

    def test_generate_datetime_invalid_format(self, capsys):
        result = exifizer.generate_photo_datetime("invalid", 1)
        assert result == "1900:01:01 00:01:00"
        captured = capsys.readouterr()
        assert "Error generating datetime" in captured.out


class TestRemoveThmFiles:
    def test_remove_thm_files(self, tmp_path):
        thm_file = tmp_path / "test.thm"
        jpg_file = tmp_path / "test.jpg"
        thm_file.write_text("thumbnail")
        jpg_file.write_text("image")
        exifizer.remove_thm_files(str(tmp_path))
        assert not thm_file.exists()
        assert jpg_file.exists()

    def test_remove_thm_files_case_insensitive(self, tmp_path):
        thm_upper = tmp_path / "test.THM"
        thm_lower = tmp_path / "test2.thm"
        thm_upper.write_text("thumbnail")
        thm_lower.write_text("thumbnail")
        exifizer.remove_thm_files(str(tmp_path))
        assert not thm_upper.exists()
        assert not thm_lower.exists()

    def test_no_thm_files_to_remove(self, tmp_path, capsys):
        jpg_file = tmp_path / "test.jpg"
        jpg_file.write_text("image")
        exifizer.remove_thm_files(str(tmp_path))
        captured = capsys.readouterr()
        assert "Removed" not in captured.out


class TestWriteExifFile:
    def test_write_exif_file(self, tmp_path):
        roll = {
            "Camera": "Canon AE-1",
            "Lens": "50mm f/1.4",
            "Filter": "UV Filter",
            "FilmStock": "Kodak Portra 400",
            "ISO": "400",
            "LoadDate": "01/15/24",
            "Subject": "Portrait",
            "ShotLocation": "New York",
            "DevelopedBy": "Local Lab",
            "FilmProcessedDate": "01/20/24",
            "Notes": "Test notes",
        }
        filepath = tmp_path / "exif.txt"
        exifizer.write_exif_file(roll, str(filepath))
        content = filepath.read_text()
        assert "Camera=Canon AE-1" in content
        assert "Lens=50mm f/1.4" in content
        assert "Film=Kodak Portra 400" in content
        assert "ISO=400" in content

    def test_write_exif_file_error(self, capsys):
        exifizer.write_exif_file({}, "/nonexistent/path/exif.txt")
        captured = capsys.readouterr()
        assert "Error writing exif file" in captured.out


class TestIsMarkdownFile:
    def test_valid_md_extension_with_hash(self, tmp_path):
        filepath = tmp_path / "test.md"
        filepath.write_text("# Title\nContent")
        assert exifizer.is_markdown_file(str(filepath)) is True

    def test_valid_md_extension_with_dash(self, tmp_path):
        filepath = tmp_path / "test.md"
        filepath.write_text("- List item\nMore content")
        assert exifizer.is_markdown_file(str(filepath)) is True

    def test_invalid_extension(self, tmp_path):
        filepath = tmp_path / "test.txt"
        filepath.write_text("# Title")
        assert exifizer.is_markdown_file(str(filepath)) is False

    def test_nonexistent_file(self):
        assert exifizer.is_markdown_file("/nonexistent/path/file.md") is False

    def test_md_file_without_markdown_content(self, tmp_path):
        filepath = tmp_path / "test.md"
        filepath.write_text("Just plain text")
        assert exifizer.is_markdown_file(str(filepath)) is False


class TestRunExiftoolCmd:
    def test_run_exiftool_cmd_success(self):
        cmd = ["echo", "test"]
        exifizer.run_exiftool_cmd(cmd, "test.jpg")

    @patch("exifizer.subprocess.run")
    def test_run_exiftool_cmd_non_zero_exit(self, mock_run, capsys):
        import subprocess

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        exifizer.VERBOSE = True
        cmd = ["exiftool", "test.jpg"]
        exifizer.run_exiftool_cmd(cmd, "test.jpg")
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        exifizer.VERBOSE = False

    @patch("exifizer.subprocess.run")
    def test_run_exiftool_cmd_exception(self, mock_run, capsys):
        mock_run.side_effect = Exception("test error")
        cmd = ["exiftool", "test.jpg"]
        exifizer.run_exiftool_cmd(cmd, "test.jpg")
        captured = capsys.readouterr()
        assert "Error running exiftool" in captured.out


class TestGetOriginalMakeModel:
    @patch("exifizer.subprocess.run")
    def test_get_make_model_success(self, mock_run):
        import subprocess

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Canon\nCanoscan 9000F", stderr=""
            ),
        ]
        result = exifizer.get_original_make_model("test.jpg")
        assert result == ("Canon", "Canoscan 9000F")

    @patch("exifizer.subprocess.run")
    def test_get_make_model_with_existing_scanner(self, mock_run):
        import subprocess

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Epson V600", stderr=""
        )
        result = exifizer.get_original_make_model("test.jpg")
        assert result == ("Epson", "V600")

    @patch("exifizer.subprocess.run")
    def test_get_make_model_failure(self, mock_run, capsys):
        import subprocess

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        result = exifizer.get_original_make_model("test.jpg")
        assert result == ("Unknown Make", "Unknown Model")
        captured = capsys.readouterr()
        assert "Unable to find scanner" in captured.out

    @patch("exifizer.subprocess.run")
    def test_get_make_model_timeout(self, mock_run, capsys):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="exiftool", timeout=10)
        result = exifizer.get_original_make_model("test.jpg")
        assert result == ("Unknown Make", "Unknown Model")


class TestMain:
    def test_main_missing_manifest(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                ["exifizer", "--film-manifest", "/nonexistent.md", "--images-dir", "/tmp"],
            ):
                exifizer.main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.out

    def test_main_missing_images_dir(self, capsys, tmp_path):
        manifest = tmp_path / "test.md"
        manifest.write_text("# Test\n- Filmstock: Test")
        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                ["exifizer", "--film-manifest", str(manifest), "--images-dir", "/nonexistent/dir"],
            ):
                exifizer.main()
        assert exc_info.value.code == 2

    def test_main_non_markdown_file(self, capsys, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not markdown")
        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                ["exifizer", "--film-manifest", str(txt_file), "--images-dir", str(tmp_path)],
            ):
                exifizer.main()
        assert exc_info.value.code == 1

    def test_main_empty_manifest(self, capsys, tmp_path):
        manifest = tmp_path / "test.md"
        manifest.write_text("# Empty\nNo rolls here")
        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                ["exifizer", "--film-manifest", str(manifest), "--images-dir", str(tmp_path)],
            ):
                exifizer.main()
        assert exc_info.value.code == 3


class TestApplyExifData:
    def test_apply_exif_data_no_images(self, tmp_path, capsys):
        rolls = [{"RollNum": "0001", "FilmStock": "Test", "LoadDate": "01/15/24"}]
        exifizer.apply_exif_data(rolls, str(tmp_path))
        captured = capsys.readouterr()
        assert "Processed 0 image files" in captured.out

    def test_apply_exif_data_with_images(self, tmp_path, capsys):
        rolls = [
            {
                "RollNum": "0001",
                "FilmStock": "Kodak Portra 400",
                "ISO": "400",
                "LoadDate": "01/15/24",
                "Camera": "Canon AE-1",
                "Lens": "50mm f/1.4",
                "FocalLength": "50",
                "Filter": "None",
                "Notes": "Test",
                "Subject": "Portrait",
                "ShotLocation": "New York",
                "FilmProcessedDate": "01/20/24",
                "DevelopedBy": "Lab",
            }
        ]
        jpg_file = tmp_path / "0000000100010.jpg"
        jpg_file.write_text("fake image")
        with patch("exifizer.get_original_make_model", return_value=("Canon", "Scanner")):
            with patch("exifizer.run_exiftool_cmd"):
                exifizer.apply_exif_data(rolls, str(tmp_path))
        captured = capsys.readouterr()
        assert "Processed 1 image files" in captured.out

    def test_apply_exif_data_filename_convention_two(self, tmp_path, capsys):
        rolls = [
            {
                "RollNum": "0001",
                "FilmStock": "Test",
                "ISO": "400",
                "LoadDate": "01/15/24",
                "Camera": "Canon AE-1",
                "Lens": "50mm f/1.4",
                "FocalLength": "50",
                "Filter": "None",
                "Notes": "Test",
                "Subject": "Portrait",
                "ShotLocation": "NYC",
                "FilmProcessedDate": "01/20/24",
                "DevelopedBy": "Lab",
            }
        ]
        jpg_file = tmp_path / "0001_5.jpg"
        jpg_file.write_text("fake image")
        with patch("exifizer.get_original_make_model", return_value=("Canon", "Scanner")):
            with patch("exifizer.run_exiftool_cmd"):
                exifizer.apply_exif_data(rolls, str(tmp_path))
        captured = capsys.readouterr()
        assert "Processed 1 image files" in captured.out

    def test_apply_exif_data_unmatched_filename(self, tmp_path, capsys):
        rolls = [{"RollNum": "0001"}]
        jpg_file = tmp_path / "invalid_name.jpg"
        jpg_file.write_text("fake image")
        exifizer.apply_exif_data(rolls, str(tmp_path))
        captured = capsys.readouterr()
        assert "Could not parse roll number" in captured.out

    def test_apply_exif_data_no_matching_roll(self, tmp_path, capsys):
        rolls = [{"RollNum": "0002"}]
        jpg_file = tmp_path / "0000000100010.jpg"
        jpg_file.write_text("fake image")
        exifizer.apply_exif_data(rolls, str(tmp_path))
        captured = capsys.readouterr()
        assert "No matching roll found" in captured.out

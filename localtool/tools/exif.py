import json
import os
import sys
import urllib.request

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from localtool.core import BaseTool


class ExifTool(BaseTool):
    name = "exif"
    help = "extract metadata from image files"

    def run(self, args: list[str] | None = None) -> int:
        parser = self.make_parser()
        parser.add_argument("-b", "--basic", action="store_true",
                            help="show basic info only (no EXIF)")
        parser.add_argument("files", nargs="+", help="image files to inspect")
        ns = self.parse(parser, args)
        if ns is None:
            return 1

        exit_code = 0
        for i, path in enumerate(ns.files):
            if i > 0:
                print()
            try:
                self._process(path, ns.basic)
            except FileNotFoundError:
                print(f"error: file not found: {path}", file=sys.stderr)
                exit_code = 1
            except OSError as e:
                print(f"error: cannot open '{path}': {e}", file=sys.stderr)
                exit_code = 1

        return exit_code

    def _process(self, path: str, basic_only: bool):
        img = Image.open(path)

        self._fmt("File", os.path.basename(path))
        self._fmt("Path", os.path.abspath(path))
        self._fmt("Size", self._fmt_size(os.path.getsize(path)))
        self._fmt("Format", img.format or "unknown")
        self._fmt("Dimensions", f"{img.width} x {img.height}")
        self._fmt("Mode", img.mode)

        if basic_only:
            img.close()
            return

        exif = img.getexif()
        if not exif:
            print("\n  No EXIF data found.")
            img.close()
            return

        sections = [
            ("Camera", ["Make", "Model", "Software"]),
            ("Image", [
                "DateTime", "DateTimeOriginal", "DateTimeDigitized",
                "Orientation", "ImageDescription", "Artist", "Copyright",
            ]),
            ("Exposure", [
                "ExposureTime", "FNumber", "ISOSpeedRatings",
                "FocalLength", "FocalLengthIn35mmFilm",
                "ExposureProgram", "MeteringMode", "Flash",
                "ExposureBiasValue", "WhiteBalance",
            ]),
            ("Lens", ["LensModel", "LensMake"]),
        ]

        for section, tag_names in sections:
            shown = False
            for tag_name in tag_names:
                value = self._get_exif_tag(exif, tag_name)
                if value is not None:
                    if not shown:
                        print(f"\n  --- {section} ---")
                        shown = True
                    self._fmt(tag_name, value)

        gps = exif.get_ifd(0x8825)
        if gps:
            lat, lon = self._parse_gps(gps)
            if lat is not None:
                print("\n  --- GPS ---")
                self._fmt("Latitude", f"{lat:.6f}")
                self._fmt("Longitude", f"{lon:.6f}")
                alt = self._get_gps_tag(gps, "GPSAltitude")
                if alt is not None:
                    alt = float(alt) if hasattr(alt, "numerator") else float(alt)
                    ref = self._get_gps_tag(gps, "GPSAltitudeRef")
                    if ref is not None:
                        if isinstance(ref, bytes):
                            ref = int(ref[0]) if ref else 0
                        sign = -1 if ref else 1
                    else:
                        sign = 1
                    self._fmt("Altitude", f"{sign * alt:.1f}m")
                address = self._reverse_geocode(lat, lon)
                if address:
                    self._fmt("Address", address)

        img.close()

    def _get_exif_tag(self, exif, name):
        for tag_id, tag_name in TAGS.items():
            if tag_name == name:
                value = exif.get(tag_id)
                if value is None:
                    return None
                return self._format_value(name, value)
        return None

    def _format_value(self, name, value):
        if isinstance(value, bytes):
            return value.decode("ascii", errors="replace").rstrip("\x00")

        if hasattr(value, "numerator"):
            f = float(value)
            if name == "ExposureTime":
                if f < 1:
                    return f"1/{value.denominator} ({f:.4f}s)"
                return f"{f:.2f}s"
            if name == "FNumber":
                return f"f/{f:.1f}"
            if name in ("FocalLength", "FocalLengthIn35mmFilm"):
                return f"{f:.1f}mm"
            if name == "ExposureBiasValue":
                return f"{f:.2f} EV"
            return str(f)

        if name == "ExposureProgram":
            return self._exposure_program(value)
        if name == "MeteringMode":
            return self._metering_mode(value)
        if name == "Flash":
            return self._flash(value)
        if name == "WhiteBalance":
            return self._white_balance(value)
        if name == "Orientation":
            return self._orientation(value)

        return str(value)

    def _get_gps_tag(self, gps, name):
        for tag_id, tag_name in GPSTAGS.items():
            if tag_name == name:
                return gps.get(tag_id)
        return None

    def _parse_gps(self, gps):
        lat = self._gps_coord(
            self._get_gps_tag(gps, "GPSLatitude"),
            self._get_gps_tag(gps, "GPSLatitudeRef"),
        )
        lon = self._gps_coord(
            self._get_gps_tag(gps, "GPSLongitude"),
            self._get_gps_tag(gps, "GPSLongitudeRef"),
        )
        return lat, lon

    def _gps_coord(self, value, ref):
        if value is None:
            return None
        deg = float(value[0]) if hasattr(value[0], "numerator") else float(value[0])
        min_ = float(value[1]) if hasattr(value[1], "numerator") else float(value[1])
        sec = float(value[2]) if hasattr(value[2], "numerator") else float(value[2])
        decimal = deg + min_ / 60.0 + sec / 3600.0
        if ref and ref in ("S", "W"):
            decimal = -decimal
        return decimal

    @staticmethod
    def _reverse_geocode(lat: float, lon: float) -> str | None:
        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
            f"&accept-language=zh"
        )
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "localtool-exif/1.0")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return data.get("display_name")
        except Exception:
            return None

    @staticmethod
    def _fmt(key: str, value):
        print(f"  {key:<20} {value}")

    @staticmethod
    def _fmt_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
            size /= 1024
        return f"{size:.1f} TB"

    @staticmethod
    def _exposure_program(v: int) -> str:
        return {
            1: "Manual", 2: "Normal", 3: "Aperture priority",
            4: "Shutter priority", 5: "Creative", 6: "Action",
            7: "Portrait", 8: "Landscape",
        }.get(v, f"Unknown ({v})")

    @staticmethod
    def _metering_mode(v: int) -> str:
        return {
            1: "Average", 2: "Center-weighted", 3: "Spot",
            4: "Multi-spot", 5: "Pattern", 6: "Partial",
        }.get(v, f"Unknown ({v})")

    @staticmethod
    def _flash(v: int) -> str:
        if v == 0:
            return "No flash"
        parts = []
        if v & 1:
            parts.append("Fired")
        if v & 5:
            parts.append("No strobe return")
        if v & 16:
            parts.append("Auto")
        if v & 64:
            parts.append("Red-eye reduction")
        return ", ".join(parts) if parts else f"Unknown ({v})"

    @staticmethod
    def _white_balance(v: int) -> str:
        return {0: "Auto", 1: "Manual"}.get(v, f"Unknown ({v})")

    @staticmethod
    def _orientation(v: int) -> str:
        return {
            1: "Normal", 3: "Rotated 180°",
            6: "Rotated 90° CW", 8: "Rotated 90° CCW",
        }.get(v, f"Unknown ({v})")



run = ExifTool.entry_point

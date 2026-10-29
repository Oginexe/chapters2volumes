#!/usr/bin/env python3
"""Group manga chapters (PDF, CBZ, CBR and/or image folders) into volumes and make one CBZ file per volume,
or, with --no-merge, just convert every file or folder to CBZ."""
import argparse
import functools
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from decimal import Decimal
from io import BytesIO
from itertools import islice
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageChops, UnidentifiedImageError

# broken or password-protected files, unsupported compression, abnormal images
ERRORS = (OSError, EOFError, KeyError, ValueError, RuntimeError, NotImplementedError,
          zipfile.BadZipFile, tarfile.TarError, Image.DecompressionBombError)
FORMATS = {".pdf": 0, ".cbz": 1, ".cbr": 2, "folder": 3}  # if a chapter is in several formats, the lowest wins
IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}  # pages read from archives
READABLE = {".jpg", ".jpeg", ".png", ".webp", ".gif"}  # pages every comic reader shows; others become PNG
SIGNATURE = b"chapters "  # start of the zip comment of every CBZ made by this program
MAX_IMAGE = 200 * 2**20  # no real page weighs 200 MB: beyond that the archive is broken or malicious


# a chapter number, optionally with decimals written as "22.5", "22_5" or "22-5"
CHAPTER = re.compile(r"(\d+)(?:[._-](\d+))?")


def to_chapter(main, part):
    """The chapter as an exact decimal number: "22_5" is 22.5, between 22 and 23.
    As with any decimal, 22.10 is 22.1, so it comes before 22.2."""
    if not part:  # no part: "" from findall, None from fullmatch
        return Decimal(int(main))
    digits = "".join(str(int(c)) for c in part)  # also turns other scripts' digits into 0-9
    return Decimal(f"{int(main)}.{digits}")


def chapter_number(file):
    """The last chapter number in the file or folder name, or None."""
    found = CHAPTER.findall(file.name if file.is_dir() else file.stem)
    return to_chapter(*found[-1]) if found else None


def fmt(n):
    return format(n, "f")


def count(n, word="chapter"):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def describe(chapters):
    if len(chapters) == 1:
        return f"chapter {fmt(chapters[0][0])} (1 chapter)"
    return f"chapters {fmt(chapters[0][0])}-{fmt(chapters[-1][0])} ({count(len(chapters))})"


def natural_key(name):
    """'page2' before 'page10'."""
    return [int(x) if x.isdecimal() else x.lower() for x in re.split(r"(\d+)", name)]


def pdfimages(options, pdf, root=None):
    # full paths: a file called "-something.pdf" must not look like an option
    command = ["pdfimages", *options, str(pdf.absolute())] + ([str(root.absolute())] if root else [])
    r = subprocess.run(command, capture_output=True, text=True)
    if r.returncode:
        reason = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "pdfimages failed"
        raise ValueError(f"unreadable PDF: {reason}")
    return r.stdout


def extract_pdf(pdf, dest, first_only):
    """The PDF's images in order: JPEGs as they are, everything else as PNG (lossless)."""
    options = ["-f", "1", "-l", "1"] if first_only else []
    rows = pdfimages(["-list", *options], pdf).splitlines()[2:]
    rows = [r.split() for r in rows if r.strip()]
    images = [(int(r[0]), int(r[1])) for r in rows if r[2] == "image"]  # (page, num): skips masks
    pages = [p for p, _ in images]
    if len(set(pages)) < len(pages):
        print(f"  WARNING: in {pdf.name} some pages are made of several images, check the page order")
    pdfimages(["-j", "-png", *options], pdf, dest / "p")
    files = {int(f.stem.rsplit("-", 1)[1]): f for f in dest.iterdir()}
    return [files[n] for _, n in images]


def is_page(name):
    """An image file inside an archive, not a hidden or system file."""
    return Path(name).suffix.lower() in IMAGES and not any(
        p.startswith(".") or p == "__MACOSX" for p in Path(name).parts)


def extract_zip(archive, dest, first_only):
    """The ZIP's (CBZ's) images in name order, copied as they are.
    Every file gets a new name: paths stored in the archive are never used."""
    with zipfile.ZipFile(archive) as z:
        entries = sorted((e for e in z.infolist() if is_page(e.filename)), key=lambda e: natural_key(e.filename))
        files = []
        for i, entry in enumerate(entries[:1] if first_only else entries):
            if entry.file_size > MAX_IMAGE:
                raise ValueError(f"image {entry.filename} is suspiciously large")
            if entry.flag_bits & 0x1:
                raise ValueError("the archive is password-protected")
            f = dest / f"p-{i:04d}{Path(entry.filename).suffix.lower()}"
            with z.open(entry) as source, open(f, "wb") as target:
                shutil.copyfileobj(source, target)
            files.append(f)
    return files


@functools.lru_cache(maxsize=None)
def find_bsdtar():
    """bsdtar, or a 'tar' that is really bsdtar (as on macOS and Windows 10/11); None if there is none."""
    for name in ("bsdtar", "tar"):
        path = shutil.which(name)
        try:
            if path and "bsdtar" in subprocess.run([path, "--version"], capture_output=True, text=True).stdout:
                return path
        except OSError:  # there, but it can't be run
            pass
    return None


def extract_rar(archive, dest, first_only):
    """The images of a RAR (CBR) or other archive in name order, copied as they are.
    bsdtar rewrites the archive as a tar stream; only regular image files are kept, under new
    names, so links and paths stored in the archive are never used."""
    pages, broken_stream = [], None
    with tempfile.TemporaryFile() as log:
        bsdtar = subprocess.Popen([find_bsdtar(), "-c", "-f", "-", "--format", "pax", f"@{archive.absolute()}"],
                                  stdout=subprocess.PIPE, stderr=log)
        try:
            with tarfile.open(fileobj=bsdtar.stdout, mode="r|") as tar:
                for i, member in enumerate(tar):
                    if not (member.isreg() and is_page(member.name)):
                        continue
                    if member.size > MAX_IMAGE:
                        raise ValueError(f"image {member.name} is suspiciously large")
                    key = natural_key(member.name)
                    if first_only and pages and key >= pages[0][0]:
                        continue  # only the first page by name is needed
                    f = dest / f"p-{i:04d}{Path(member.name).suffix.lower()}"
                    with tar.extractfile(member) as source, open(f, "wb") as target:
                        shutil.copyfileobj(source, target)
                    if first_only and pages:
                        pages.pop()[1].unlink()
                    pages.append((key, f))
        except tarfile.TarError as e:
            broken_stream = e  # the real reason is usually in bsdtar's messages, checked below
        finally:
            bsdtar.stdout.close()
            failed = bsdtar.wait()
        if failed:
            log.seek(0)
            lines = log.read().decode(errors="replace").strip().splitlines()
            reason = re.sub(r"^\S*tar\S*: ", "", lines[0]) if lines else "bsdtar failed"  # the first line says why
            raise ValueError(f"unreadable archive: {reason}")
    if broken_stream:
        raise ValueError(f"unreadable archive: {broken_stream}")
    return [f for _, f in sorted(pages, key=lambda p: p[0])]


def folder_pages(folder):
    """The images of a chapter folder (subfolders too) in name order; hidden files are skipped."""
    return sorted((p for p in folder.rglob("*") if p.is_file() and is_page(str(p.relative_to(folder)))),
                  key=lambda p: natural_key(str(p.relative_to(folder))))


def needs_bsdtar(file):
    return file.is_file() and file.suffix.lower() != ".pdf" and not zipfile.is_zipfile(file)


def extract(file, dest, first_only=False):
    """Pages of a chapter. Archives are recognised by their content: many ".cbr" files are really ZIPs."""
    if file.is_dir():
        pages = folder_pages(file)  # your own image files: used where they are, nothing is copied
        return pages[:1] if first_only else pages
    if file.suffix.lower() == ".pdf":
        return extract_pdf(file, dest, first_only)
    if zipfile.is_zipfile(file):
        return extract_zip(file, dest, first_only)
    return extract_rar(file, dest, first_only)


def open_page(f):
    try:
        return Image.open(f)
    except UnidentifiedImageError:
        raise ValueError("a page is not a readable image (damaged file, or password-protected archive?)") from None


def cover_check(file, args):
    """(is_cover, colour_score) for the chapter's first image."""
    with tempfile.TemporaryDirectory() as t:
        images = extract(file, Path(t), first_only=True)
        if not images:
            return False, 0.0
        with open_page(images[0]) as im:
            if im.height <= im.width:
                return False, 0.0
            hsv = im.convert("RGB").resize((150, 150)).convert("HSV")
            s = hsv.getchannel(1).point(lambda x: 255 * (x > 60))
            v = hsv.getchannel(2).point(lambda x: 255 * (x > 40))
            score = ImageChops.darker(s, v).histogram()[255] / (150 * 150)
    return args.detect == "portrait" or score > args.threshold, score


def group(chapters, args):
    volumes = []
    for n, file in chapters:
        cover, score = False, 0.0
        if args.detect != "none":
            try:
                cover, score = cover_check(file, args)
            except ERRORS as e:
                print(f"  WARNING: {file.name}: {e}. Can't tell if it is a cover, treating it as a normal chapter")
        size = len(volumes[-1]) if volumes else 0
        if n in args.starts:
            new, why = True, "set by you with --starts"
        elif n in args.not_starts:
            new, why = False, "set by you with --not-starts"
        elif args.max_chapters and size >= args.max_chapters:
            new, why = True, f"the volume already has {count(size)}, see --max-chapters"
        elif cover and volumes and size < args.min_chapters:
            new, why = False, f"ignored: the volume only has {count(size)}, see --min-chapters"
        else:
            new, why = cover, "cover"
        if volumes and (new or cover or n in args.not_starts):
            score_text = f"colour {score:.2f} -> " if args.detect == "color" else ""
            print(f"  ch. {fmt(n)}: {score_text}{'NEW VOLUME' if new else 'no new volume'} ({why})")
        if new or not volumes:
            volumes.append([])
        volumes[-1].append((n, file))
    return volumes


def encode(im, image_format):
    if image_format == "JPEG" and im.mode not in ("RGB", "L"):
        im = im.convert("L" if im.mode in ("1", "LA", "I", "I;16") else "RGB")
    elif image_format == "PNG" and im.mode in ("CMYK", "YCbCr", "LAB"):
        im = im.convert("RGB")
    buf = BytesIO()
    im.save(buf, image_format, **({"quality": 95} if image_format == "JPEG" else {}))
    return buf.getvalue()


def content_size(file):
    return sum(p.stat().st_size for p in folder_pages(file)) if file.is_dir() else file.stat().st_size


def signature(chapters, args):
    """What a CBZ is made of (source files and their sizes), stored as the zip comment."""
    return (SIGNATURE + f"{'|'.join(f'{f.name}:{content_size(f)}' for _, f in chapters)}; "
            f"split={args.split}; left_first={args.left_first}".encode())


def kept_safe(dest, chapters, present, args):
    """True if dest exists and rebuilding it could lose pages, so it must be left alone:
    it wasn't made by this program, or some of the files it was made from are no longer here."""
    if args.overwrite or not dest.exists():
        return False
    comment = zip_comment(dest)
    if comment == signature(chapters, args):
        return False  # same content: it is simply skipped as already done
    if not comment.startswith(SIGNATURE):
        return True
    made_from = comment[len(SIGNATURE):].decode(errors="replace").split("; split=")[0].split("|")
    return not {entry.rsplit(":", 1)[0] for entry in made_from} <= present


def zip_comment(cbz):
    try:
        with zipfile.ZipFile(cbz) as z:
            return z.comment
    except (OSError, zipfile.BadZipFile):
        return b""


def comic_info(info, pages, args):
    """Metadata read by most comic readers: title, series, number and reading direction.
    The tags must stay in this order: the ComicInfo schema requires it."""
    tags = [("Title", info.get("title")), ("Series", info.get("series")), ("Number", info.get("number")),
            ("Volume", info.get("volume")), ("Summary", info.get("summary")), ("PageCount", pages),
            ("Manga", "No" if args.left_first else "YesAndRightToLeft")]
    body = "".join(f"  <{tag}>{escape(str(value))}</{tag}>\n" for tag, value in tags if value is not None)
    return f'<?xml version="1.0" encoding="utf-8"?>\n<ComicInfo>\n{body}</ComicInfo>\n'


def make_cbz(chapters, dest, info, args):
    """Writes the CBZ to a .part file and renames it only at the end: never a half-written CBZ."""
    partial = dest.with_name(dest.name + ".part")
    k, file = 0, None
    try:
        # strict_timestamps=False: pages dated before 1980 (common after some extractions) are accepted
        with tempfile.TemporaryDirectory() as t, \
                zipfile.ZipFile(partial, "w", zipfile.ZIP_STORED, strict_timestamps=False) as z:
            z.comment = signature(chapters, args)
            for i, (_, file) in enumerate(chapters):
                folder = Path(t) / str(i)
                folder.mkdir()
                files = extract(file, folder)
                if not files:
                    print(f"  WARNING: {file.name} contains no pages")
                for f in files:
                    suffix = f.suffix.lower()
                    with open_page(f) as im:
                        if not (args.split and im.width > im.height):  # single page: kept whole
                            k += 1
                            if suffix in READABLE:
                                z.write(f, f"{k:04d}{suffix}")  # copied exactly as it is
                            else:
                                z.writestr(f"{k:04d}.png", encode(im, "PNG"))  # e.g. TIFF: lossless PNG
                            continue
                        image_format, ext = ("JPEG", ".jpg") if suffix in (".jpg", ".jpeg") else ("PNG", ".png")
                        m = im.width // 2
                        right = im.crop((m, 0, im.width, im.height))
                        left = im.crop((0, 0, m, im.height))
                        for half in ((left, right) if args.left_first else (right, left)):
                            k += 1
                            z.writestr(f"{k:04d}{ext}", encode(half, image_format))
            file = None  # from here on, a problem is not a chapter's fault
            if not k:
                raise ValueError("no pages found")
            z.writestr("ComicInfo.xml", comic_info(info, k, args))
        partial.replace(dest)
    except BaseException as e:
        partial.unlink(missing_ok=True)
        if isinstance(e, ERRORS) and file is not None:
            raise ValueError(f"{file.name}: {e}") from e  # says which chapter is the problem
        raise
    return k


def chapter_arg(text):
    m = CHAPTER.fullmatch(text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"'{text}' is not a chapter number (e.g. 22, 22.5, 22_5 or 22-5)")
    return to_chapter(*m.groups())


def number_list(text):
    try:
        return {chapter_arg(x) for x in text.split(",") if x.strip()}
    except argparse.ArgumentTypeError:
        raise argparse.ArgumentTypeError(
            f"'{text}': use chapter numbers separated by commas, e.g. 25,37 or 22.5,22_6") from None


def folder_path(text):
    return Path(text).expanduser()  # "~/Manga" works even inside quotes


def in_range(n, args):
    return (args.first is None or n >= args.first) and (args.last is None or n <= args.last)


def check_tools(files):
    """Stops with clear instructions if a tool needed by these files is missing."""
    if any(f.is_file() and f.suffix.lower() == ".pdf" for f in files) and not shutil.which("pdfimages"):
        sys.exit("Reading PDFs needs pdfimages: install poppler (Arch: sudo pacman -S poppler, "
                 "Debian/Ubuntu: sudo apt install poppler-utils, Fedora: sudo dnf install poppler-utils, "
                 "macOS: brew install poppler, Windows: winget install --id oschwartz10612.Poppler -e).")
    if any(needs_bsdtar(f) for f in files) and not find_bsdtar():
        sys.exit("Some files are not ZIP files (usually CBR/RAR, or damaged files): reading them needs "
                 "bsdtar. Install libarchive (Arch: sudo pacman -S libarchive, "
                 "Debian/Ubuntu: sudo apt install libarchive-tools, Fedora: sudo dnf install bsdtar; "
                 "macOS and Windows 10/11 already have it).")


def convert_each(files, args, series):
    """--no-merge: every file or folder becomes its own CBZ, with the same name as the original."""
    if args.detect != "color" or args.starts or args.not_starts or args.max_chapters or args.first_volume != 1:
        print("Note: --no-merge doesn't group anything, so the volume options "
              "(--detect, --starts, --max-chapters, --first-volume...) are ignored.")
    jobs, names, made_here = [], {}, 0
    for f in files:  # sorted by format: if a name exists in several formats, the first one in FORMATS wins
        if f.suffix.lower() == ".cbz" and zip_comment(f).startswith(SIGNATURE):
            made_here += 1  # made by this program
            continue
        name, n = (f.name if f.is_dir() else f.stem), chapter_number(f)
        if (n is None and (args.first, args.last) != (None, None)) or (n is not None and not in_range(n, args)):
            continue
        if name.lower() in names:
            print(f"WARNING: {name} is there twice: using {names[name.lower()].name}, ignoring {f.name}")
            continue
        names[name.lower()] = f
        jobs.append((natural_key(name), name, n, f))
    if made_here:
        print(f"Note: ignoring {count(made_here, 'file')} already made by this program.")
    if not jobs:
        sys.exit(f"No files to convert (PDF, CBZ, CBR or folders of images) found in {args.folder}")
    check_tools([f for *_, f in jobs])
    jobs.sort()

    # lower case: on Windows and macOS "Vol 1.CBZ" and "Vol 1.cbz" are the same file
    originals = {str(f.resolve()).lower() for f in files}
    present = {f.name for f in files}
    print(f"{count(len(jobs), 'file')} to convert, one CBZ each:")
    for _, name, n, f in jobs:
        dest, warn = args.output / f"{name}.cbz", ""
        if str(dest.resolve()).lower() in originals:
            warn = "  <-- it would replace your original file: choose another folder with -o"
        elif kept_safe(dest, [(n, f)], present, args):
            warn = "  <-- a different CBZ with this name already exists: it will NOT be replaced"
        print(f"  {f.name} -> {name}.cbz{warn}")
    if args.dry_run:
        print("\nPreview finished, nothing was created.")
        return

    args.output.mkdir(parents=True, exist_ok=True)
    print()
    failed, kept = [], []
    for i, (_, name, n, f) in enumerate(jobs, 1):
        dest = args.output / f"{name}.cbz"
        progress = f"{name} ({i}/{len(jobs)})"
        if str(dest.resolve()).lower() in originals:  # never write over an original file
            print(f"{progress}: ERROR: {dest.name} would replace your original file: choose another folder with -o")
            failed.append(name)
            continue
        if not args.overwrite and zip_comment(dest) == signature([(n, f)], args):
            print(f"{progress}: already done, skipping")
            continue
        if kept_safe(dest, [(n, f)], present, args):
            print(f"{progress}: KEPT: {dest.name} already exists and wasn't made from this file, so it is left as it is")
            kept.append(name)
            continue
        print(progress, flush=True)
        try:
            pages = make_cbz([(n, f)], dest, {"title": name, "series": series,
                                              "number": None if n is None else fmt(n)}, args)
        except ERRORS as e:
            print(f"  ERROR: {e}")
            failed.append(name)
            continue
        print(f"  {count(pages, 'page')} -> {dest.name}")
    if kept:
        print(f"\nNOT replaced: {kept}. Those CBZ files already exist in the output folder: "
              "choose another folder with -o, or use --overwrite to replace them.")
    if failed:
        sys.exit(f"\nNOT converted: {failed}. Check those files and run the same command again.")
    if kept:
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=folder_path,
                   help="folder with the chapters (PDF, CBZ and/or CBR files, or folders of images)")
    p.add_argument("-o", "--output", type=folder_path, default=Path("output"), metavar="FOLDER",
                   help="where to save the volumes (default: output)")
    p.add_argument("-s", "--series", metavar="NAME", help="series name used in the file names (default: the folder's name)")
    p.add_argument("--detect", choices=("color", "portrait", "none"), default="color",
                   type=lambda s: "color" if s == "colour" else s,  # both spellings work
                   help="what marks a volume's first chapter: a colour portrait page (default), "
                        "any portrait page, or nothing (manual mode: use --starts and/or --max-chapters)")
    p.add_argument("--threshold", type=float, default=0.25, metavar="X",
                   help="share of coloured pixels for a page to count as a colour cover, 0-1 (default 0.25)")
    p.add_argument("--min-chapters", type=int, default=5, metavar="N", help="minimum chapters per volume (default 5)")
    p.add_argument("--max-chapters", type=int, metavar="N", help="maximum chapters per volume (default: no limit)")
    p.add_argument("--starts", type=number_list, default=set(), metavar="LIST",
                   help="chapters that surely start a volume, e.g. 25,37")
    p.add_argument("--not-starts", type=number_list, default=set(), metavar="LIST",
                   help="chapters that surely don't start a volume, e.g. 42")
    p.add_argument("--from", dest="first", type=chapter_arg, metavar="N", help="first chapter to use")
    p.add_argument("--to", dest="last", type=chapter_arg, metavar="N", help="last chapter to use")
    p.add_argument("--first-volume", type=int, default=1, metavar="N", help="number of the first volume (default 1)")
    p.add_argument("--no-merge", action="store_true",
                   help="don't group into volumes: turn every file or folder into its own CBZ with the same name "
                        "(e.g. when the files are already volumes)")
    p.add_argument("--no-split", dest="split", action="store_false", help="don't cut double pages in half")
    p.add_argument("--left-first", action="store_true", help="left half first (western reading order)")
    p.add_argument("--dry-run", action="store_true", help="preview only, create nothing")
    p.add_argument("--overwrite", action="store_true",
                   help="rebuild and replace existing CBZ files, even if already done or made from files that are gone")
    args = p.parse_args()
    if args.max_chapters is not None and args.max_chapters < 1:
        p.error("--max-chapters must be at least 1")
    if args.first_volume < 0:
        p.error("--first-volume can't be negative")

    if not args.folder.is_dir():
        sys.exit(f"The folder {args.folder} doesn't exist.")
    series = args.series or args.folder.resolve().name
    # characters that Windows (and other systems) don't allow in file names
    file_series = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", series).rstrip(". ") or "Manga"
    # any capitalisation: on Windows and macOS "my manga - volume 01.cbz" is the same file
    volume_name = re.compile(re.escape(file_series) + r" - Volume (\d+)\.cbz", re.IGNORECASE)

    def chapter_format(f):
        if f.name.startswith("."):  # hidden files (e.g. "._Ch 1.pdf" made by Macs) are not chapters
            return None
        if f.is_dir():
            return "folder" if folder_pages(f) else None  # a folder counts only if it holds images
        return f.suffix.lower() if f.suffix.lower() in FORMATS else None

    candidates = []
    for f in args.folder.iterdir():
        kind = chapter_format(f)
        if kind:
            candidates.append((FORMATS[kind], f.name, f))
    candidates.sort()  # by format: if a chapter exists in several formats, the first one in FORMATS wins
    if args.no_merge:
        return convert_each([f for *_, f in candidates], args, series)
    chosen, old_volumes = {}, 0
    for *_, f in candidates:
        if f.suffix.lower() == ".cbz" and (volume_name.fullmatch(f.name) or zip_comment(f).startswith(SIGNATURE)):
            old_volumes += 1  # a volume made by this program, not a chapter
            continue
        n = chapter_number(f)
        if n is None:
            print(f"WARNING: {f.name} has no number in its name, skipped")
        elif n in chosen:
            print(f"WARNING: chapter {fmt(n)} is there twice: using {chosen[n].name}, ignoring {f.name}")
        elif in_range(n, args):
            chosen[n] = f
    if old_volumes:
        print(f"Note: ignoring {count(old_volumes, 'volume')} already made by this program.")
    chapters = sorted(chosen.items())
    if not chapters:
        sys.exit(f"No chapters (PDF, CBZ, CBR or folders of images) found in {args.folder}")
    check_tools([f for _, f in chapters])

    found = [n for n, _ in chapters]
    whole = sorted({int(n) for n in found})
    gaps = [(a, b) for a, b in zip(whole, whole[1:]) if b - a > 1]
    if gaps:  # without building huge lists if a name contains a giant number
        total = sum(b - a - 1 for a, b in gaps)
        first = list(islice((m for a, b in gaps for m in range(a + 1, b)), 20))
        more = f" and {total - 20} more" if total > 20 else ""
        print(f"WARNING: chapters missing from the numbering: {first}{more}")
    for option, numbers in (("--starts", args.starts), ("--not-starts", args.not_starts)):
        if numbers - set(found):
            print(f"WARNING: {option} lists chapters that aren't among the ones being used: "
                  f"{[fmt(n) for n in sorted(numbers - set(found))]}")
    if args.starts & args.not_starts:
        print(f"WARNING: chapters in both --starts and --not-starts (--starts wins): "
              f"{[fmt(n) for n in sorted(args.starts & args.not_starts)]}")
    if args.detect == "none" and not args.starts and not args.max_chapters:
        print("Note: --detect none without --starts or --max-chapters puts everything in one volume.")

    print(f"{count(len(chapters))} found, " +
          ("grouping them..." if args.detect == "none" else "looking for covers..."))
    volumes = group(chapters, args)
    width = max(2, len(str(args.first_volume + len(volumes) - 1)))
    plan = [(args.first_volume + i, chs, args.output / f"{file_series} - Volume {args.first_volume + i:0{width}d}.cbz")
            for i, chs in enumerate(volumes)]
    present = {f.name for *_, f in candidates}  # every chapter file in the folder, even outside --from/--to

    print()
    for number, chs, dest in plan:
        warn = "  <-- few chapters?" if len(chs) < args.min_chapters and args.detect != "none" else ""
        if kept_safe(dest, chs, present, args):
            warn += "  <-- a different volume with this name already exists: it will NOT be replaced"
        print(f"Volume {number:0{width}d}: {describe(chs)}{warn}")
    if len(volumes) == 1 and len(chapters) > 1 and args.detect != "none" and not (args.starts or args.not_starts):
        print("\nTip: no volume start was found, so everything is in one volume. If the covers aren't in colour, "
              "try --detect portrait, or split by hand with --detect none plus --starts and/or --max-chapters.")
    if args.dry_run:
        print("\nPreview finished, nothing was created.")
        return

    args.output.mkdir(parents=True, exist_ok=True)
    print()
    failed, kept = [], []
    for i, (number, chs, dest) in enumerate(plan, 1):
        progress = f"Volume {number:0{width}d} ({i}/{len(volumes)})"
        if not args.overwrite and zip_comment(dest) == signature(chs, args):
            print(f"{progress}: already done with the same chapters, skipping ({dest.name})")
            continue
        if kept_safe(dest, chs, present, args):  # e.g. a volume made earlier from chapters that are gone
            print(f"{progress}: KEPT: {dest.name} already exists and can't be rebuilt from the chapters here, "
                  "so it is left as it is")
            kept.append(number)
            continue
        print(f"{progress}: {describe(chs)}", flush=True)
        try:
            pages = make_cbz(chs, dest, {"series": series, "number": number, "volume": number,
                                         "summary": describe(chs).capitalize()}, args)
        except ERRORS as e:
            print(f"  ERROR: {e}")
            failed.append(number)
            continue
        print(f"  {count(pages, 'page')} -> {dest.name}")
    if kept:
        existing = [int(m.group(1)) for m in map(volume_name.fullmatch, os.listdir(args.output)) if m]
        print(f"\nNOT replaced: volumes {kept}, because volumes with the same name already exist.\n"
              f"To add these chapters as new volumes after the ones you have, run the same command with "
              f"--first-volume {max(existing, default=max(kept)) + 1}.\n"
              "To replace the old volumes anyway, use --overwrite.")
    if failed:
        sys.exit(f"\nVolumes NOT created: {failed}. Check those chapters and run the same command again.")
    if kept:
        sys.exit(1)


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        sys.exit("This program needs Python 3.8 or newer.")
    # a terminal that can't show a character (e.g. in a file name) must not stop the program
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped. No half-written file was left: run the same command again to continue.")
    except BrokenPipeError:  # the output went to a program that stopped reading it (e.g. "| head")
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())  # as the Python docs recommend
        sys.exit(1)

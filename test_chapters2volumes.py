#!/usr/bin/env python3
"""Self-test: builds fake chapters (PDF, CBZ and CBR) and checks volumes, page order, splitting and errors.

Run with:  python3 test_chapters2volumes.py
"""
import os
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile
import zlib
from io import BytesIO
from pathlib import Path

from PIL import Image

SCRIPT = Path(__file__).with_name("chapters2volumes.py")


def pdf(path, pages):
    pages[0].save(path, save_all=True, append_images=pages[1:])


def cbz(path, pages):  # {name inside the archive: image}
    with zipfile.ZipFile(path, "w") as z:
        for name, im in pages.items():
            buf = BytesIO()
            im.save(buf, "TIFF" if name.endswith(".tif") else "JPEG")
            z.writestr(name, buf.getvalue())


def jpeg(im):
    buf = BytesIO()
    im.save(buf, "JPEG")
    return buf.getvalue()


def rar(path, pages):  # a real RAR 4 archive with stored (uncompressed) files: no rar tool needed
    def block(kind, flags, fields, data=b""):
        head = struct.pack("<BHH", kind, flags, 7 + len(fields)) + fields
        return struct.pack("<H", zlib.crc32(head) & 0xFFFF) + head + data

    out = b"Rar!\x1a\x07\x00" + block(0x73, 0, bytes(6))
    for name, im in pages.items():
        data, n = jpeg(im), name.encode()
        fields = struct.pack("<IIBIIBBHI", len(data), len(data), 3, zlib.crc32(data), 0x5A210000, 20, 0x30,
                             len(n), 0o100644) + n
        out += block(0x74, 0x8000, fields, data)
    path.write_bytes(out + block(0x7B, 0x4000, b""))


def cover():  # portrait, full colour
    return Image.new("RGB", (600, 900), "red")


def single():  # portrait, grey: not a colour cover
    return Image.new("RGB", (600, 900), "gray")


def double(mode="RGB"):  # landscape: left half black, right half white
    im = Image.new("L", (1200, 900), 255)
    im.paste(0, (0, 0, 600, 900))
    return im.convert(mode)


def run(*args, ok=True, env=None):
    """Runs the program; unless the test gives --series, the series is named after the chapters' folder."""
    args = [str(a) for a in args]
    if "--series" not in args and args and not args[0].startswith("-"):
        args += ["--series", Path(args[0]).name]
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)
    print(r.stdout, r.stderr)
    assert (r.returncode == 0) == ok, "unexpected exit code"
    return r.stdout + r.stderr


def pages(cbz_file):
    with zipfile.ZipFile(cbz_file) as z:
        return [Image.open(BytesIO(z.read(n))) for n in sorted(z.namelist()) if not n.endswith(".xml")]


def shade(im):  # "black" / "white" / "grey" / "colour" at the centre of the page
    r, g, b = im.convert("RGB").getpixel((im.width // 2, im.height // 2))
    if max(r, g, b) - min(r, g, b) > 60:
        return "colour"
    return "black" if r < 60 else "white" if r > 200 else "grey"


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    src = tmp / "Test Series"
    src.mkdir()
    pdf(src / "Test Series - Chapter 1.pdf", [cover(), double()])
    pdf(src / "Test Series - Chapter 2.pdf", [single(), double()])
    pdf(src / "Test Series - Chapter 2.5.PDF", [double("1")])  # bilevel page, upper-case extension
    # chapter 3 is missing on purpose
    # chapter 4 only as CBZ: "page10" must come after "page2"; hidden and non-image files are skipped
    cbz(src / "Test Series - Chapter 4.cbz",
        {"ch4/page10.jpg": double(), "ch4/page2.jpg": cover(), "__MACOSX/._page2.jpg": single(),
         "ch4/page11.tif": double("CMYK")})
    pdf(src / "Test Series - Chapter 5.pdf", [cover(), double()])  # colour page, but too soon: not a cover
    cbz(src / "Test Series - Chapter 5.cbz", {"x.jpg": single()})  # same chapter as the PDF: ignored
    (src / "notes.txt").write_text("not a chapter")
    (src / "._Test Series - Chapter 1.pdf").write_bytes(b"macOS junk")  # hidden file: ignored

    out = tmp / "out"
    log = run(src, "-o", out, "--min-chapters", "2", "--dry-run")
    assert not out.exists(), "--dry-run must not create anything"
    assert "[3]" in log, "missing chapter 3 not reported"
    assert "ignoring Test Series - Chapter 5.cbz" in log, "duplicate chapter not reported"

    run(src, "-o", out, "--min-chapters", "2")
    assert sorted(p.name for p in out.iterdir()) == ["Test Series - Volume 01.cbz", "Test Series - Volume 02.cbz"]

    v1 = pages(out / "Test Series - Volume 01.cbz")
    assert [shade(p) for p in v1] == ["colour", "white", "black", "grey", "white", "black", "white", "black"]
    assert v1[0].size == (600, 900), "the cover must stay whole"
    subprocess.run(["pdfimages", "-j", "-l", "1", src / "Test Series - Chapter 1.pdf", tmp / "c"], check=True)
    with zipfile.ZipFile(out / "Test Series - Volume 01.cbz") as z:
        assert z.read("0001.jpg") == (tmp / "c-000.jpg").read_bytes(), "the cover must not be re-compressed"
    assert all(p.width < p.height for p in v1), "every double page must be split"

    v2 = pages(out / "Test Series - Volume 02.cbz")
    assert [shade(p) for p in v2] == ["colour", "white", "black", "white", "black", "colour", "white", "black"]
    with zipfile.ZipFile(src / "Test Series - Chapter 4.cbz") as a, zipfile.ZipFile(out / "Test Series - Volume 02.cbz") as b:
        assert a.read("ch4/page2.jpg") == b.read("0001.jpg"), "CBZ pages must not be re-compressed"
        info = b.read("ComicInfo.xml").decode()
    tags = ["<Series>Test Series</Series>", "<Number>2</Number>", "<Volume>2</Volume>",
            "<PageCount>8</PageCount>", "<Manga>YesAndRightToLeft</Manga>"]  # in the order the schema requires
    assert all(t in info for t in tags), "ComicInfo.xml lacks a tag"
    assert [info.index(t) for t in tags] == sorted(info.index(t) for t in tags), "ComicInfo.xml tags out of order"

    run(src, "-o", out, "--min-chapters", "2", "--left-first", "--overwrite")
    assert [shade(p) for p in pages(out / "Test Series - Volume 02.cbz")][1:3] == ["black", "white"]

    run(src, "-o", out, "--min-chapters", "2", "--no-split", "--overwrite")
    assert len(pages(out / "Test Series - Volume 01.cbz")) == 5
    assert len(pages(out / "Test Series - Volume 02.cbz")) == 5

    run(src, "-o", out, "--min-chapters", "2", "--starts", "2", "--not-starts", "4,5", "--overwrite")
    assert len(list(out.iterdir())) == 2  # volumes now: 1 | 2, 2.5, 4, 5
    assert len(pages(out / "Test Series - Volume 02.cbz")) == 13

    # manual modes, checked on the preview
    def plan(*extra):
        return [line.split(": ")[1] for line in run(src, "--dry-run", *extra).splitlines() if line.startswith("Volume ")]

    assert plan("--detect", "none") == ["chapters 1-5 (5 chapters)"]
    assert "Tip:" in run(src, "--dry-run", "--threshold", "1"), "a run with no covers found must suggest the manual modes"
    assert plan("--detect", "none", "--starts", "4") == ["chapters 1-2.5 (3 chapters)", "chapters 4-5 (2 chapters)"]
    assert plan("--detect", "none", "--max-chapters", "2") == [
        "chapters 1-2 (2 chapters)", "chapters 2.5-4 (2 chapters)", "chapter 5 (1 chapter)"]
    assert plan("--detect", "portrait", "--min-chapters", "1") == [
        "chapter 1 (1 chapter)", "chapters 2-2.5 (2 chapters)", "chapter 4 (1 chapter)", "chapter 5 (1 chapter)"]
    log = run(src, "--dry-run", "--min-chapters", "2", "--first-volume", "7")
    assert "Volume 07:" in log and "Volume 08:" in log
    run(src, "--max-chapters", "0", ok=False)
    assert "separated by commas" in run(src, "--starts", "a,b", ok=False)
    assert plan("--detect", "colour") == plan("--detect", "color"), "both spellings must work"

    # output in the same folder as the chapters: the volumes must never be read back as chapters
    run(src, "-o", src, "--min-chapters", "2")
    log = run(src, "-o", src, "--min-chapters", "2")
    assert "5 chapters found" in log and log.count("already done") == 2, "volumes were mistaken for chapters"
    pdf(src / "Test Series - Chapter 2.5.PDF", [double("1"), double("1")])  # a better scan of one chapter
    log = run(src, "-o", src, "--min-chapters", "2")
    assert log.count("already done") == 1, "a volume with a replaced chapter must be rebuilt"

    # CBZ chapters only, and poppler not installed: it must still work
    only_cbz = tmp / "Only CBZ"
    only_cbz.mkdir()
    cbz(only_cbz / "c1.cbz", {"1.jpg": cover(), "2.jpg": double()})
    run(only_cbz, "-o", tmp / "out2", env={"PATH": ""})
    assert len(pages(tmp / "out2" / "Only CBZ - Volume 01.cbz")) == 3
    assert "needs pdfimages" in run(src, "--dry-run", ok=False, env={"PATH": ""})

    # CBR (RAR) chapters, and archives whose extension lies about their content
    arc = tmp / "Archives"
    arc.mkdir()
    rar(arc / "c1.cbr", {"ch/p10.jpg": double(), "ch/p2.jpg": cover()})  # real RAR: "p2" comes first
    cbz(arc / "c2.cbr", {"1.jpg": double(), "2.tif": single()})  # a ".cbr" that is really a ZIP; a TIFF page
    rar(arc / "c3.cbz", {"1.jpg": double()})  # a ".cbz" that is really a RAR
    secret = tmp / "secret.jpg"
    secret.write_bytes(jpeg(single()))
    with tarfile.open(arc / "c4.cbr", "w") as t:  # a link to a file outside the archive: must be ignored
        link = tarfile.TarInfo("2.jpg")
        link.type, link.linkname = tarfile.SYMTYPE, str(secret)
        t.addfile(link)
        page = jpeg(double())
        info = tarfile.TarInfo("1.jpg")
        info.size = len(page)
        t.addfile(info, BytesIO(page))
    cbz(arc / "c5.cbz", {})  # a chapter with no pages: a warning, not a failure
    cbz(arc / "c4.5.cbz", {"p1²2.jpg": double(), "p1²3.jpg": double()})  # "²" between digits in page names
    log = run(arc, "-o", tmp / "out3")
    assert "c5.cbz contains no pages" in log
    v = pages(tmp / "out3" / "Archives - Volume 01.cbz")
    assert [shade(p) for p in v] == ["colour", "white", "black", "white", "black", "grey",
                                     "white", "black", "white", "black", "white", "black", "white", "black"], \
        "wrong pages from CBR/renamed archives"
    with zipfile.ZipFile(tmp / "out3" / "Archives - Volume 01.cbz") as z:
        assert z.read("0001.jpg") == jpeg(cover()), "CBR pages must not be re-compressed"
        assert z.namelist()[5] == "0006.png", "a TIFF page must become a PNG every reader can show"
    assert "needs bsdtar" in run(arc, "--dry-run", ok=False, env={"PATH": ""})
    (arc / "c6.cbr").write_bytes(b"Rar!\x1a\x07\x00 broken")
    log = run(arc, "-o", tmp / "out3", ok=False)
    assert "ERROR: c6.cbr: unreadable archive" in log and "Traceback" not in log

    # folders of images as chapters, next to an archive; folders without images are not chapters
    fol = tmp / "Folders"
    (fol / "Ch 1" / "sub").mkdir(parents=True)
    cover().save(fol / "Ch 1" / "p2.JPG")  # upper-case extension
    double().save(fol / "Ch 1" / "sub" / "p10.jpg")  # pages in a subfolder, name order "p2" < "sub/p10"
    single().save(fol / "Ch 1" / ".thumb.jpg")  # hidden: skipped
    (fol / "Ch 1.5").mkdir()  # "1.5" in a folder name is a chapter number, not an extension
    double().save(fol / "Ch 1.5" / "1.png")
    os.utime(fol / "Ch 1" / "p2.JPG", (0, 0))  # a whole page dated 1970: ZIP can't store dates before 1980
    (fol / "Extras 3").mkdir()  # no images: not a chapter
    (fol / "Extras 3" / "notes.txt").write_text("-")
    cbz(fol / "Ch 2.cbz", {"1.jpg": double()})
    log = run(fol, "-o", fol / "out", "--series", 'Re:Zero? "Test"')
    assert "3 chapters found" in log and "chapters 1-2 (3 chapters)" in log
    made = fol / "out" / "Re-Zero- -Test- - Volume 01.cbz"  # characters Windows forbids are replaced
    assert [shade(p) for p in pages(made)] == ["colour", "white", "black", "white", "black", "white", "black"]
    with zipfile.ZipFile(made) as z:
        assert z.read("0001.jpg") == (fol / "Ch 1" / "p2.JPG").read_bytes(), "folder pages must be copied as they are"
        assert '<Series>Re:Zero? "Test"</Series>' in z.read("ComicInfo.xml").decode(), "the real title stays in the metadata"
    assert "already done" in run(fol, "-o", fol / "out", "--series", 'Re:Zero? "Test"')
    double().save(fol / "Ch 1.5" / "2.png")  # a page added to a folder: its volume must be rebuilt
    assert "already done" not in run(fol, "-o", fol / "out", "--series", 'Re:Zero? "Test"')

    # no "bsdtar" command, only a "tar" that is bsdtar (as on macOS and Windows): CBR still works
    fake_bin = tmp / "bin"
    fake_bin.mkdir()
    (fake_bin / "tar").symlink_to(subprocess.run(["which", "bsdtar"], capture_output=True, text=True).stdout.strip())
    only_cbr = tmp / "Only CBR"
    only_cbr.mkdir()
    rar(only_cbr / "Capítulo 1.cbr", {"1.jpg": cover(), "2.jpg": double()})  # non-ASCII name, see below
    run(only_cbr, "-o", tmp / "out5", env={"PATH": str(fake_bin)})
    assert len(pages(tmp / "out5" / "Only CBR - Volume 01.cbz")) == 3

    # a terminal that can't show "é" must not stop the program
    cbz(only_cbr / "Extra é.cbz", {})  # no number in the name: its name is printed in a warning
    assert "Extra ?.cbz" in run(only_cbr, "--dry-run", env={"PATH": str(fake_bin), "PYTHONIOENCODING": "ascii"})

    # chapter parts written as 22.5, 22_5 or 22-5: decimals, so after 22 and before 23, and 22.10 (= 22.1) before 22.2
    parts = tmp / "Parts"
    parts.mkdir()
    for name in ("Ch 22", "Ch 22_2", "Ch 22.5", "Ch 22_10", "Ch 23", "Ch 24-5", "Ch 24", "Ch 34-3", "Vol.02 Ch.035"):
        cbz(parts / f"{name}.cbz", {"1.jpg": single()})
    cbz(parts / "Ch 22-5.cbz", {"1.jpg": single()})  # the same chapter as "22.5", written differently

    def order(*extra):
        return [line.split(": ")[1].split(" (")[0] for line in run(parts, "--dry-run", "--detect", "none", *extra)
                .splitlines() if line.startswith("Volume ")]

    assert order("--max-chapters", "1") == ["chapter 22", "chapter 22.10", "chapter 22.2", "chapter 22.5", "chapter 23",
                                            "chapter 24", "chapter 24.5", "chapter 34.3", "chapter 35"]
    assert "chapter 22.5 is there twice" in run(parts, "--dry-run", "--detect", "none")
    assert order("--starts", "22_5,24") == ["chapters 22-22.2", "chapters 22.5-23", "chapters 24-35"]
    assert order("--starts", "22.2") == ["chapters 22-22.10", "chapters 22.2-35"], "22.10 must come before 22.2"
    assert order("--starts", "22.100") == ["chapter 22", "chapters 22.10-35"], "22.100 is the same number as 22.10"
    assert order("--from", "22-5", "--to", "24") == ["chapters 22.5-24"]
    assert "chapters missing from the numbering: [25, 26, 27, 28, 29, 30, 31, 32, 33]" in run(parts, "--dry-run")

    # --no-merge: files that are already volumes, each converted on its own and keeping its name
    vols = tmp / "Volumes"
    (vols / "Vol 4").mkdir(parents=True)
    pdf(vols / "Vol 1.pdf", [cover(), double()])
    rar(vols / "Vol 2.cbr", {"1.jpg": cover(), "2.jpg": double()})
    cbz(vols / "Extra.cbz", {"1.jpg": single()})  # no number in the name: fine here
    cbz(vols / "Upper.CBZ", {"1.jpg": single()})  # on Windows/macOS, "Upper.cbz" would be this very file
    cbz(vols / "Vol 3.cbz", {"1.jpg": single()})
    pdf(vols / "Vol 3.pdf", [cover(), double(), double()])  # same name as the CBZ: the PDF wins
    double().save(vols / "Vol 4" / "1.png")
    extra_before = (vols / "Extra.cbz").read_bytes()
    log = run(vols, "-o", tmp / "out6", "--no-merge", "--starts", "2")
    assert "Vol 3 is there twice: using Vol 3.pdf, ignoring Vol 3.cbz" in log and "are ignored" in log
    assert sorted(p.name for p in (tmp / "out6").iterdir()) == [
        "Extra.cbz", "Upper.cbz", "Vol 1.cbz", "Vol 2.cbz", "Vol 3.cbz", "Vol 4.cbz"]
    assert [len(pages(tmp / "out6" / f"{v}.cbz")) for v in ("Vol 1", "Vol 2", "Vol 3", "Vol 4", "Extra")] == [3, 3, 5, 2, 1]
    with zipfile.ZipFile(tmp / "out6" / "Vol 2.cbz") as z:
        info = z.read("ComicInfo.xml").decode()
    assert "<Title>Vol 2</Title>" in info and "<Number>2</Number>" in info and "<Volume>" not in info
    assert run(vols, "-o", tmp / "out6", "--no-merge").count("already done") == 6
    assert run(vols, "-o", tmp / "out6", "--no-merge", "--from", "2", "--to", "3").count("already done") == 2
    log = run(vols, "-o", vols, "--no-merge", ok=False)  # same folder: Extra.cbz and Vol 3.cbz would be overwritten
    for name in ("Extra.cbz", "Vol 3.cbz", "Upper.cbz"):
        assert f"{name} would replace your original file" in log, f"{name} was not protected"
    assert (vols / "Extra.cbz").read_bytes() == extra_before, "an original file was changed"
    assert not (vols / "Upper.cbz").exists(), "a file differing only in case was written next to the original"
    log = run(vols, "-o", vols, "--no-merge", ok=False)  # still failing only for the real originals
    assert "files already made by this program" in log
    assert "Vol 1.cbz would replace" not in log, "a CBZ made by this program was taken for an original"
    assert log.count("already done") == 3, "the CBZ files made on the first run must be recognised as done"

    # the series name is always chosen by the user: never taken from a folder name
    named = tmp / "Some Series" / "Volumi"
    named.mkdir(parents=True)
    cbz(named / "Some Series [Volume 01].cbz", {"1.jpg": cover()})
    no_series = subprocess.run([sys.executable, str(SCRIPT), str(named), "--no-merge", "--dry-run"],
                               capture_output=True, text=True)
    assert no_series.returncode != 0 and "--series" in no_series.stderr, "--series must be required"
    assert "can't be empty" in run(named, "--no-merge", "--series", " ", "--dry-run", ok=False)
    assert "no letters or digits" in run(named, "--no-merge", "--series", "...", "--dry-run", ok=False)
    assert "Series: Other Name\n" in run(named, "-o", tmp / "out9", "--no-merge", "--series", "Other Name")
    with zipfile.ZipFile(tmp / "out9" / "Some Series [Volume 01].cbz") as z:
        assert "<Series>Other Name</Series>" in z.read("ComicInfo.xml").decode()

    # new chapters added next to volumes made earlier, whose chapters are gone: the old volumes must survive
    later = tmp / "Later"
    later.mkdir()
    cbz(later / "Later - Volume 01.cbz", {"1.jpg": cover(), "2.jpg": single(), "3.jpg": single()})  # made long ago
    cbz(later / "later - volume 05.CBZ", {"1.jpg": single()})  # other capitalisation: still one of the volumes
    old_volume = (later / "Later - Volume 01.cbz").read_bytes()
    cbz(later / "Ch 157.cbz", {"1.jpg": cover()})
    cbz(later / "Ch 158.cbz", {"1.jpg": single()})
    assert "will NOT be replaced" in run(later, "-o", later, "--dry-run")
    assert "--first-volume 6" in run(later, "-o", later, "--dry-run"), "the preview must suggest the right number"
    log = run(later, "-o", later, ok=False)
    assert "--first-volume 6" in log and (later / "Later - Volume 01.cbz").read_bytes() == old_volume, \
        "an existing volume that can't be rebuilt was replaced"
    assert "2 chapters found" in log, "an old volume was taken for a chapter"
    assert "Nothing was created" in log and len(list(later.iterdir())) == 4, "volumes with wrong numbers were made"
    run(later, "-o", later, "--first-volume", "6")
    assert len(pages(later / "Later - Volume 06.cbz")) == 2 and (later / "Later - Volume 01.cbz").read_bytes() == old_volume

    # an old volume made under another series name is still a volume, never a chapter
    renamed = tmp / "Renamed"
    renamed.mkdir()
    cbz(renamed / "Old Name - Volume 01.cbz", {"1.jpg": cover()})
    cbz(renamed / "Ch 2.cbz", {"1.jpg": cover()})
    cbz(renamed / "Ch 3.cbz", {"1.jpg": single()})
    log = run(renamed, "--series", "New Name", "--dry-run")
    assert "ignoring 1 volume already made" in log and "2 chapters found" in log, "an old volume was taken for a chapter"

    # a volume made by this program, then one of its chapters deleted: it can't be rebuilt, so it is kept
    gone = tmp / "Gone"
    gone.mkdir()
    cbz(gone / "c1.cbz", {"1.jpg": cover()})
    cbz(gone / "c2.cbz", {"1.jpg": single()})
    run(gone, "-o", tmp / "out7")
    made = (tmp / "out7" / "Gone - Volume 01.cbz").read_bytes()
    (gone / "c1.cbz").unlink()
    cbz(gone / "c3.cbz", {"1.jpg": single()})
    assert "will NOT be replaced" in run(gone, "-o", tmp / "out7", ok=False)
    assert (tmp / "out7" / "Gone - Volume 01.cbz").read_bytes() == made, "a volume whose chapter is gone was replaced"
    run(gone, "-o", tmp / "out7", "--overwrite")  # unless you ask for it
    assert (tmp / "out7" / "Gone - Volume 01.cbz").read_bytes() != made

    # --no-merge: a CBZ with the same name already in the output folder, not made from this file: kept
    (tmp / "out8").mkdir()
    cbz(tmp / "out8" / "Vol 1.cbz", {"1.jpg": single()})
    foreign = (tmp / "out8" / "Vol 1.cbz").read_bytes()
    assert "will NOT be replaced" in run(vols, "-o", tmp / "out8", "--no-merge", "--dry-run")
    assert "would replace your original file" in run(vols, "-o", vols, "--no-merge", "--dry-run")
    assert "KEPT" in run(vols, "-o", tmp / "out8", "--no-merge", ok=False)
    assert (tmp / "out8" / "Vol 1.cbz").read_bytes() == foreign

    # odd names: a leading dash, and a huge number (a download ID) read as the chapter number
    odd = tmp / "Odd"
    odd.mkdir()
    pdf(odd / "-c1.pdf", [cover(), double()])
    pdf(odd / "c2 1698765432.pdf", [double()])
    r = subprocess.run([sys.executable, str(SCRIPT), ".", "--dry-run", "--series", "Odd"], cwd=odd, capture_output=True, text=True, timeout=60)
    print(r.stdout, r.stderr)
    assert r.returncode == 0 and "and 1698765410 more" in r.stdout and "2 chapters found" in r.stdout

    # damaged chapters: reported by name, the run goes on, nothing half-written is left
    (src / "Test Series - Chapter 6.pdf").write_text("broken file")
    with zipfile.ZipFile(src / "Test Series - Chapter 7.cbz", "w") as z:  # CBZ with a corrupt image
        z.writestr("1.jpg", b"not an image")
    log = run(src, "-o", out, "--min-chapters", "2", "--not-starts", "4,5", ok=False)
    assert "ERROR: Test Series - Chapter 6.pdf" in log, "the broken chapter must be named in the error"
    assert "WARNING: Test Series - Chapter 7.cbz: a page is not a readable image" in log and "Traceback" not in log, \
        "a broken CBZ must be reported clearly, not crash"
    assert not list(out.glob("*.part")), "no half-written files must be left behind"

print("ALL CHECKS PASSED")

# chapters2volumes

**Turn a folder of manga chapters (PDF, CBZ, CBR or folders of images) into one comic-book file (CBZ) per volume.**

Works on **Linux, macOS and Windows**.

🇮🇹 [Leggi in italiano](README.it.md)

---

## What problem does it solve?

Scanned manga often come as **one file per chapter**, hundreds of them, and every image is often a scan of **two facing pages side by side**.
That is awkward to read on an e-reader, a tablet or a phone.

`chapters2volumes` takes that folder and gives you back:

- **one file per volume** (e.g. `My Manga - Volume 01.cbz`), so 500 chapters become ~45 tidy files;
- **one page per screen**: each two-page scan is cut in half and the halves are put in the correct reading order;
- **the cover first**, kept whole;
- **volume information inside each file**, so your reader app shows the series and volume number and knows the pages turn right to left.

The chapters can be **PDF, CBZ or CBR files, or folders of images (JPG, PNG, WebP…), in any mix**.
The result is **always CBZ**: the standard "comic book" format that almost every comic/manga reader opens
(e.g. YACReader, CDisplayEx, Komga, Kavita, Mihon/Tachiyomi, KOReader, Calibre).

Already have whole volumes and just want them as CBZ? See [Convert only, without grouping](#convert-only-without-grouping).

## How does it work? (in plain words)

1. **It finds where each volume begins.**
   In a printed volume, the first chapter usually opens with the **cover**: a single, upright, full-colour page.
   The program looks at the first page of every chapter: if it is upright *and* colourful, a new volume starts there.
   No colour covers in your manga? See [Manual mode](#manual-mode-when-there-are-no-colour-covers).

2. **It avoids mistakes.**
   Some chapters open with a colour page that is *not* a cover. To avoid splitting a volume too early,
   a new volume is accepted only if the current one already has a minimum number of chapters (you choose it).
   And if it still gets something wrong, you can tell it exactly which chapters start (or don't start) a volume.

3. **It cuts the double pages.**
   Every image wider than it is tall is a two-page scan, and it is cut in the middle.
   Manga is read **right to left**, so the right half comes first:

   ```
   ┌───────────┬───────────┐
   │  page 2   │  page 1   │   →   page 1, then page 2
   └───────────┴───────────┘
   ```

   Covers and single pages stay whole. You can reverse the order (for western comics) or turn the cutting off.

4. **It packs each volume** into a `.cbz` file, with pages numbered in order.

## Is it safe for my files?

- **Your original files are never modified, moved or deleted.** The program only reads them.
- **Preview mode** (`--dry-run`) shows how the volumes would be split, without creating anything.
- If a chapter is **missing** from the numbering (e.g. 1, 2, 4), it warns you and carries on.
- If a file is **damaged** or password-protected, it tells you which one and carries on with the other volumes.
- If you **stop it** halfway (Ctrl+C), no half-written file is left behind. Run the same command again and it continues from where it stopped.
- **No quality loss** for pages that are not cut: they are copied exactly as they are.
  Cut halves of JPEG pages are saved at high quality (95); other pages are saved losslessly (PNG).
  The only pages that are converted are TIFF and BMP ones, which many readers can't show: they become lossless PNG.
- **Archives are opened safely**: only the images are taken out, under new names, so a malicious CBZ/CBR
  cannot write files elsewhere on your computer or sneak other files into your volumes.
- It works **offline** and sends nothing anywhere. The files it creates contain no personal data (no user names or folder paths).

## Who can use it?

Anyone with a computer running **Linux, macOS or Windows 10/11**. It is a single Python file: there is nothing to compile.

| System | Status |
|---|---|
| Linux (Arch) | fully tested |
| Other Linux distributions, macOS | expected to work (same tools, same commands) |
| Windows 10/11 | expected to work; reading **CBR** files relies on Windows' built-in `tar`, which may not open every RAR file (if it fails, use [WSL](https://learn.microsoft.com/windows/wsl/install)) |

If you try it on a system marked "expected to work", please report how it went.

## What you need

| What | Why | Needed if… |
|---|---|---|
| **Python 3.8 or newer** | runs the program | always |
| **Pillow** (Python library) | reads and cuts images | always |
| **poppler** (`pdfimages`) | takes the pages out of PDFs | you have PDF chapters |
| **bsdtar** | opens CBR (RAR) files | you have CBR chapters |

CBZ files and folders of images need nothing more than Python and Pillow.

### Linux

| Distribution | One command installs everything |
|---|---|
| Arch / Manjaro | `sudo pacman -S python python-pillow poppler libarchive` |
| Debian / Ubuntu / Mint | `sudo apt install python3 python3-pil poppler-utils libarchive-tools` |
| Fedora | `sudo dnf install python3 python3-pillow poppler-utils bsdtar` |

### macOS

With [Homebrew](https://brew.sh): `brew install python pillow poppler` (bsdtar is already part of macOS).

### Windows 10/11

1. Install Python from [python.org](https://www.python.org/downloads/) (tick **"Add python.exe to PATH"** during the installation).
2. Open **PowerShell** or **Terminal** in the program's folder and install Pillow: `py -m pip install -r requirements.txt`
3. Only for PDF chapters, install poppler: `winget install --id oschwartz10612.Poppler -e`, then open a new terminal.
4. bsdtar is already part of Windows (it is called `tar`).

On Windows, write `py` instead of `python3` in the commands below.

### With pip, on any system

The Python part can also be installed with pip, using the included `requirements.txt`:

```
python3 -m pip install -r requirements.txt
```

> On many Linux systems pip refuses to install packages system-wide. Then use a virtual environment inside the program's folder:
> `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, and run `.venv/bin/python3` instead of `python3`.
> poppler and bsdtar are not Python packages: install them as shown above.

### Getting the program

On GitHub: green **Code** button → **Download ZIP**, then unzip it in a folder you like.

## How to use it: 3 steps

Open a terminal in the folder where `chapters2volumes.py` is.
In the examples, the chapters are in the folder `~/Manga/My Manga` (`~` means "your home folder";
on Windows you can also write a full path such as `"C:\Manga\My Manga"`).
**Use quotes** around names that contain spaces.

### 1. Preview (creates nothing)

```
python3 chapters2volumes.py "~/Manga/My Manga" --series "My Manga" --min-chapters 8 --dry-run
```

You will see something like:

```
Series: My Manga
156 chapters found, looking for covers...
  ch. 12: colour 0.93 -> NEW VOLUME (cover)
  ch. 25: colour 0.46 -> NEW VOLUME (cover)
  ...
Volume 01: chapters 1-11 (11 chapters)
Volume 02: chapters 12-24 (13 chapters)
...
```

The *colour* number goes from 0 (black and white) to 1 (all colour).

### 2. Check, and fix if needed

Do the volumes look right (most printed volumes have 8–13 chapters)? If not, add one of these to the command and preview again:

| If… | add | meaning |
|---|---|---|
| a volume starts in the wrong place | `--starts 25,37` | chapters 25 and 37 **do** start a volume |
| a colour page was taken for a cover | `--not-starts 42` | chapter 42 does **not** start a volume |
| volumes are split too often | `--min-chapters 10` | a volume has at least 10 chapters |
| some volumes are far too long | `--max-chapters 13` | a volume has at most 13 chapters |
| covers are missed (pale colours) | `--threshold 0.15` | lower = a page needs less colour to count as a cover (default 0.25) |
| normal pages are taken for covers | `--threshold 0.4` | higher = stricter |
| everything ends up in one volume | see [Manual mode](#manual-mode-when-there-are-no-colour-covers) | |

### 3. Create the volumes

Same command, **without** `--dry-run`, plus where to save the result (`-o`):

```
python3 chapters2volumes.py "~/Manga/My Manga" --series "My Manga" --min-chapters 8 -o "~/Manga/Volumes"
```

It shows the progress (`Volume 03 (3/46): ...`). When it's done, open the `.cbz` files with your reader.

## Manual mode (when there are no colour covers)

Many manga have black-and-white covers, or no cover at all in the scans. Then the automatic search finds nothing
and puts every chapter in one volume (the program tells you so). You have three ways out:

- **Covers in black and white** — count any upright single page that opens a chapter as a cover:
  ```
  python3 chapters2volumes.py "~/Manga/My Manga" --detect portrait --min-chapters 8 --dry-run
  ```
- **You know where volumes start** (e.g. from a list of volumes on a wiki) — give the first chapter of each volume:
  ```
  python3 chapters2volumes.py "~/Manga/My Manga" --detect none --starts 1,10,19,28,37 --dry-run
  ```
- **You just want volumes of the same size** — e.g. one volume every 10 chapters:
  ```
  python3 chapters2volumes.py "~/Manga/My Manga" --detect none --max-chapters 10 --dry-run
  ```

You can combine them: `--starts` and `--max-chapters` together, or `--not-starts` to fix a single mistake.
When the preview looks right, run the same command without `--dry-run` and with `-o`.

## Convert only, without grouping

If your files are already whole volumes (or you simply want each chapter as its own CBZ), add `--no-merge`:
every file or folder becomes one CBZ **with the same name** (`Vol 3.pdf` → `Vol 3.cbz`, `Vol 4.cbr` → `Vol 4.cbz`).
Double pages are still cut and the volume information is still added; files without a number in the name are fine too.

```
python3 chapters2volumes.py "~/Manga/My Volumes" --no-merge --dry-run
python3 chapters2volumes.py "~/Manga/My Volumes" --no-merge -o "~/Manga/CBZ"
```

Your original files are never overwritten: if a CBZ would get the same name as an original CBZ in the same folder,
the program refuses and asks you to choose another folder with `-o`.

## All options

| Option | What it does | Default |
|---|---|---|
| *folder* (first argument) | folder with the chapters (PDF, CBZ, CBR, folders of images, or a mix) | required |
| `-o`, `--output` | where to save the volumes | `output` |
| `-s`, `--series` | series name, used in the file names and in the volume information | the folder's name (or the folder above, if the folder is called e.g. `Volumes`, `Volumi`, `Chapters`, `CBZ`) |
| `--dry-run` | preview only, creates nothing | off |
| `--detect` | how a volume start is recognised: `color` or `colour` (colour cover), `portrait` (any upright single page), `none` (manual) | `color` |
| `--threshold X` | how colourful a page must be to count as a cover (0–1) | 0.25 |
| `--min-chapters N` | minimum chapters per volume | 5 |
| `--max-chapters N` | maximum chapters per volume | no limit |
| `--starts 25,37` | chapters that surely start a volume | none |
| `--not-starts 42` | chapters that surely do not start a volume | none |
| `--from N` / `--to N` | use only chapters from N / up to N | all |
| `--first-volume N` | number of the first volume (e.g. to continue a series you have already converted) | 1 |
| `--no-merge` | don't group: turn every file or folder into its own CBZ with the same name | off |
| `--no-split` | do not cut double pages | cut |
| `--left-first` | left half first (western reading order) | right half first |
| `--overwrite` | rebuild and replace existing CBZ files, even if already done or made from files that are gone | keep them |

`python3 chapters2volumes.py --help` shows the same list.

## Good to know

- **How chapters are numbered:** the program uses the **last number in the file or folder name**:
  `My Manga - Chapter 012.pdf` → chapter 12.
  Two numbers joined by `.`, `_` or `-` are read as a **decimal number**: `22.5`, `22_5` and `22-5` are all 22.5,
  which comes after 22 and before 23. As with any decimal, `22.10` is 22.1, so it comes **before** `22.2`
  (and `22.1` and `22.10` count as the same chapter: you get a warning if both are there).
  The same goes for the options: `--starts 22_5`, `--from 22.5`.
  Avoid other numbers at the end of the name (e.g. `Chapter 12 (2024).pdf` would be read as chapter 2024).
- **Folders of images:** each folder inside the main folder is a chapter (e.g. `My Manga/Chapter 12/001.jpg`).
  Its pages are taken in name order, subfolders included; folders without images are ignored.
- **Mixed formats:** all formats can be in the same folder. If the same chapter exists in more than one format,
  the program uses the PDF, then the CBZ, then the CBR, then the folder, and warns you.
- **Mislabelled archives are fine:** many ".cbr" files are really ZIP files (and some ".cbz" are really RAR).
  The program looks at what is inside the file, not at its extension.
- **Inside a CBZ or CBR**, pages are taken in name order (`page2` comes before `page10`); hidden and system files are ignored.
- **Password-protected archives** can't be read: the program tells you which chapter it is.
- **Series names** with characters that Windows doesn't allow in file names (`: ? * " < > |`) are fine:
  those characters are replaced by `-` in the file name, while the real title is kept in the volume information.
- **Running it again** is safe and quick: volumes already made with the same chapters are skipped.
  If you add or replace chapters (or pages in a chapter folder), only the volumes that changed are rebuilt.
- **Your existing volumes are never lost.** A CBZ that is already in the output folder is replaced only if it can be
  rebuilt without losing anything: it was made by this program and all the files it was made from are still there.
  Otherwise it is kept as it is, the preview marks it with `will NOT be replaced`, and the program tells you what to do.
  When grouping into volumes, nothing at all is created in that case, so that the volume numbers stay in order.
  `--overwrite` replaces it anyway.
- **New chapters later on?** If you still have all the old chapters, just add the new ones and run the same command:
  only the volumes that change are rebuilt. If the old chapters are gone (you kept only the volumes), add the new
  chapters and run the command: the program keeps your volumes and tells you the `--first-volume` number to use,
  so that the new volumes come after the old ones.
- **Saving the volumes in the same folder as the chapters** is fine: the program recognises its own volumes and never mistakes them for chapters.
- **Limits:** the cut is always made exactly in the middle of the image; a page made of several images in a PDF is not reassembled (you get a warning).

## Problems?

| Message | What to do |
|---|---|
| `Reading PDFs needs pdfimages` | install poppler (see *What you need*) |
| `... reading them needs bsdtar` | install bsdtar (see *What you need*) |
| `ModuleNotFoundError: No module named 'PIL'` | install Pillow (see *What you need*) |
| `This program needs Python 3.8 or newer` | install a newer Python |
| `The folder ... doesn't exist` | the folder path is wrong: check it, and use quotes if it has spaces |
| `No chapters (PDF, CBZ, CBR or folders of images) found` | the folder contains no chapter files or folders with a number in the name |
| `Tip: no volume start was found` | your covers are probably not in colour: see [Manual mode](#manual-mode-when-there-are-no-colour-covers) |
| `a page is not a readable image` | that chapter is damaged or password-protected: replace it |
| `Volumes NOT created: [...]` / `NOT converted: [...]` | the line marked `ERROR` names the damaged file: replace it and run the same command again |
| `would replace your original file` | with `--no-merge`, save into another folder with `-o` |
| `will NOT be replaced` / `Nothing was created` | volumes with those names already exist and can't be rebuilt: if your chapters are new, use the `--first-volume N` the program suggests; to rebuild the old volumes, use `--overwrite` |
| `KEPT` / `NOT replaced` (with `--no-merge`) | a CBZ with that name already exists in the output folder: choose another folder with `-o`, or use `--overwrite` |

## Checking that it works (optional)

`test_chapters2volumes.py` creates fake chapters (PDF, CBZ, real RAR files and folders of images) in a temporary folder
and checks volumes, page order, cutting, chapter parts, manual mode, `--no-merge`, error handling, safety and more:

```
python3 test_chapters2volumes.py
```

It ends with `ALL CHECKS PASSED` and leaves nothing behind. It needs poppler and bsdtar, and runs on Linux and macOS.

## Please note

This tool is meant for organising copies of works **you are entitled to own and read**. It contains no manga and downloads nothing.

## License

[MIT](LICENSE): you can use, copy, change and share it freely, as long as you keep the copyright notice.

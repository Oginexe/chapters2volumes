# chapters2volumes

**Trasforma una cartella di capitoli manga (PDF, CBZ, CBR o cartelle di immagini) in un file a fumetti (CBZ) per ogni volume.**

Funziona su **Linux, macOS e Windows**.

🇬🇧 [Read in English](README.md)

---

## A cosa serve?

I manga scansionati spesso arrivano come **un file per capitolo**, centinaia di file, e spesso ogni immagine è la scansione di **due pagine affiancate**.
Così è scomodo leggerli su e-reader, tablet o telefono.

`chapters2volumes` prende quella cartella e ti restituisce:

- **un file per volume** (es. `Il Mio Manga - Volume 01.cbz`): 500 capitoli diventano circa 45 file ordinati;
- **una pagina per schermata**: ogni scansione doppia viene tagliata a metà e le due metà vengono messe nell'ordine di lettura giusto;
- **la copertina per prima**, intera;
- **le informazioni del volume dentro ogni file**, così il tuo lettore mostra serie e numero del volume e sa che le pagine si girano da destra a sinistra.

I capitoli possono essere **file PDF, CBZ o CBR, oppure cartelle di immagini (JPG, PNG, WebP…), anche mischiati tra loro**.
Il risultato è **sempre CBZ**: il formato standard dei fumetti digitali, che quasi ogni lettore di fumetti e manga apre
(es. YACReader, CDisplayEx, Komga, Kavita, Mihon/Tachiyomi, KOReader, Calibre).

Hai già i volumi completi e vuoi solo trasformarli in CBZ? Vedi [Solo conversione, senza unire](#solo-conversione-senza-unire).

> Il programma "parla" inglese: i messaggi e le opzioni sono in inglese. Questa guida spiega tutto in italiano.

## Come funziona? (in parole semplici)

1. **Trova dove comincia ogni volume.**
   In un volume stampato, il primo capitolo di solito si apre con la **copertina**: una pagina singola, verticale, tutta a colori.
   Il programma guarda la prima pagina di ogni capitolo: se è verticale *e* colorata, lì comincia un nuovo volume.
   Il tuo manga non ha copertine a colori? Vedi la [modalità manuale](#modalità-manuale-quando-non-ci-sono-copertine-a-colori).

2. **Evita gli errori.**
   Alcuni capitoli si aprono con una pagina a colori che *non* è una copertina. Per non chiudere un volume troppo presto,
   un nuovo volume viene accettato solo se quello in corso ha già un numero minimo di capitoli (lo scegli tu).
   E se sbaglia comunque, puoi dirgli esattamente quali capitoli iniziano (o non iniziano) un volume.

3. **Taglia le doppie pagine.**
   Ogni immagine più larga che alta è una scansione di due pagine, e viene tagliata a metà.
   I manga si leggono **da destra a sinistra**, quindi prima viene la metà destra:

   ```
   ┌───────────┬───────────┐
   │ pagina 2  │ pagina 1  │   →   pagina 1, poi pagina 2
   └───────────┴───────────┘
   ```

   Copertine e pagine singole restano intere. Puoi invertire l'ordine (per i fumetti occidentali) o non tagliare affatto.

4. **Impacchetta ogni volume** in un file `.cbz`, con le pagine numerate in ordine.

## I miei file sono al sicuro?

- **I file originali non vengono mai modificati, spostati o cancellati.** Il programma li legge e basta.
- La **modalità anteprima** (`--dry-run`) mostra come verrebbero divisi i volumi, senza creare niente.
- Se nella numerazione **manca un capitolo** (es. 1, 2, 4), ti avvisa e continua.
- Se un file è **rovinato** o protetto da password, ti dice quale e continua con gli altri volumi.
- Se lo **interrompi** a metà (Ctrl+C), non resta nessun file a metà. Rilancia lo stesso comando e riprende da dove si era fermato.
- **Nessuna perdita di qualità** per le pagine che non vengono tagliate: sono copiate così come sono.
  Le metà delle pagine JPEG sono salvate ad alta qualità (95); le altre pagine senza nessuna perdita (PNG).
  Le uniche pagine convertite sono quelle TIFF e BMP, che molti lettori non sanno mostrare: diventano PNG, senza perdita.
- **Gli archivi vengono aperti in modo sicuro**: si estraggono solo le immagini, con nomi nuovi, quindi un CBZ/CBR
  malevolo non può scrivere file in giro per il tuo computer né infilare altri file nei tuoi volumi.
- Funziona **senza internet** e non invia niente a nessuno. I file che crea non contengono dati personali (né nomi utente né percorsi di cartelle).

## Chi può usarlo?

Chiunque abbia un computer con **Linux, macOS o Windows 10/11**. È un solo file Python: non c'è niente da compilare.

| Sistema | Stato |
|---|---|
| Linux (Arch) | provato a fondo |
| Altre distribuzioni Linux, macOS | dovrebbe funzionare (stessi strumenti, stessi comandi) |
| Windows 10/11 | dovrebbe funzionare; per leggere i **CBR** usa il `tar` già incluso in Windows, che potrebbe non aprire tutti i file RAR (in quel caso usa [WSL](https://learn.microsoft.com/it-it/windows/wsl/install)) |

Se lo provi su un sistema segnato "dovrebbe funzionare", segnala com'è andata.

## Cosa serve

| Cosa | A cosa serve | Serve se… |
|---|---|---|
| **Python 3.8 o più recente** | fa funzionare il programma | sempre |
| **Pillow** (libreria Python) | legge e taglia le immagini | sempre |
| **poppler** (`pdfimages`) | estrae le pagine dai PDF | hai capitoli in PDF |
| **bsdtar** | apre i file CBR (RAR) | hai capitoli in CBR |

Per i CBZ e le cartelle di immagini bastano Python e Pillow.

### Linux

| Distribuzione | Un solo comando installa tutto |
|---|---|
| Arch / Manjaro | `sudo pacman -S python python-pillow poppler libarchive` |
| Debian / Ubuntu / Mint | `sudo apt install python3 python3-pil poppler-utils libarchive-tools` |
| Fedora | `sudo dnf install python3 python3-pillow poppler-utils bsdtar` |

### macOS

Con [Homebrew](https://brew.sh): `brew install python pillow poppler` (bsdtar fa già parte di macOS).

### Windows 10/11

1. Installa Python da [python.org](https://www.python.org/downloads/) (durante l'installazione spunta **"Add python.exe to PATH"**).
2. Apri **PowerShell** o **Terminale** nella cartella del programma e installa Pillow: `py -m pip install -r requirements.txt`
3. Solo se hai capitoli in PDF, installa poppler: `winget install --id oschwartz10612.Poppler -e`, poi apri un nuovo terminale.
4. bsdtar fa già parte di Windows (si chiama `tar`).

Su Windows, nei comandi qui sotto scrivi `py` al posto di `python3`.

### Con pip, su qualsiasi sistema

La parte Python si può installare anche con pip, usando il file `requirements.txt` incluso:

```
python3 -m pip install -r requirements.txt
```

> Su molti sistemi Linux pip si rifiuta di installare pacchetti per tutto il sistema. In quel caso usa un ambiente virtuale nella cartella del programma:
> `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`, e poi usa `.venv/bin/python3` al posto di `python3`.
> poppler e bsdtar non sono pacchetti Python: installali come spiegato sopra.

### Scaricare il programma

Su GitHub: pulsante verde **Code** → **Download ZIP**, poi estrai lo ZIP in una cartella a tua scelta.

## Come si usa: 3 passi

Apri un terminale nella cartella dove si trova `chapters2volumes.py`.
Negli esempi i capitoli sono nella cartella `~/Manga/Il Mio Manga` (`~` vuol dire "la tua cartella personale";
su Windows puoi anche scrivere un percorso completo come `"C:\Manga\Il Mio Manga"`).
**Metti le virgolette** attorno ai nomi che contengono spazi.

### 1. Anteprima (non crea niente)

```
python3 chapters2volumes.py "~/Manga/Il Mio Manga" --series "Il Mio Manga" --min-chapters 8 --dry-run
```

Vedrai qualcosa del genere:

```
156 chapters found, looking for covers...
  ch. 12: colour 0.93 -> NEW VOLUME (cover)
  ch. 25: colour 0.46 -> NEW VOLUME (cover)
  ...
Volume 01: chapters 1-11 (11 chapters)
Volume 02: chapters 12-24 (13 chapters)
...
```

Cioè: 156 capitoli trovati; al capitolo 12 c'è una copertina (colore 0.93), quindi lì comincia un nuovo volume; il volume 01 va dal capitolo 1 all'11.
Il numero del *colore* va da 0 (bianco e nero) a 1 (tutto a colori).

### 2. Controlla, e correggi se serve

I volumi hanno senso? (La maggior parte dei volumi stampati ha 8–13 capitoli.) Se no, aggiungi al comando una di queste opzioni e rifai l'anteprima:

| Se… | aggiungi | significa |
|---|---|---|
| un volume comincia nel punto sbagliato | `--starts 25,37` | i capitoli 25 e 37 **iniziano** un volume |
| una pagina a colori è stata presa per copertina | `--not-starts 42` | il capitolo 42 **non** inizia un volume |
| i volumi sono spezzati troppo spesso | `--min-chapters 10` | un volume ha almeno 10 capitoli |
| alcuni volumi sono lunghissimi | `--max-chapters 13` | un volume ha al massimo 13 capitoli |
| alcune copertine non vengono trovate (colori tenui) | `--threshold 0.15` | più basso = basta meno colore per essere una copertina (normale: 0.25) |
| pagine normali vengono prese per copertine | `--threshold 0.4` | più alto = più severo |
| finisce tutto in un unico volume | vedi la [modalità manuale](#modalità-manuale-quando-non-ci-sono-copertine-a-colori) | |

### 3. Crea i volumi

Stesso comando, **senza** `--dry-run`, più dove salvare il risultato (`-o`):

```
python3 chapters2volumes.py "~/Manga/Il Mio Manga" --series "Il Mio Manga" --min-chapters 8 -o "~/Manga/Volumi"
```

Mostra l'avanzamento (`Volume 03 (3/46): ...`). Quando ha finito, apri i file `.cbz` con il tuo lettore.

## Modalità manuale (quando non ci sono copertine a colori)

Molti manga hanno copertine in bianco e nero, oppure nelle scansioni la copertina non c'è proprio. In quel caso la ricerca automatica non trova niente
e mette tutti i capitoli in un unico volume (il programma te lo dice con un messaggio `Tip:`). Hai tre soluzioni:

- **Copertine in bianco e nero**: conta come copertina qualsiasi pagina singola verticale che apre un capitolo:
  ```
  python3 chapters2volumes.py "~/Manga/Il Mio Manga" --detect portrait --min-chapters 8 --dry-run
  ```
- **Sai dove iniziano i volumi** (es. da un elenco dei volumi su una wiki): indica il primo capitolo di ogni volume:
  ```
  python3 chapters2volumes.py "~/Manga/Il Mio Manga" --detect none --starts 1,10,19,28,37 --dry-run
  ```
- **Vuoi solo volumi della stessa dimensione**: per esempio un volume ogni 10 capitoli:
  ```
  python3 chapters2volumes.py "~/Manga/Il Mio Manga" --detect none --max-chapters 10 --dry-run
  ```

Puoi combinarle: `--starts` e `--max-chapters` insieme, oppure `--not-starts` per correggere un singolo errore.
Quando l'anteprima va bene, rilancia lo stesso comando senza `--dry-run` e con `-o`.

## Solo conversione, senza unire

Se i tuoi file sono già volumi completi (o vuoi semplicemente ogni capitolo come CBZ a sé), aggiungi `--no-merge`:
ogni file o cartella diventa un CBZ **con lo stesso nome** (`Vol 3.pdf` → `Vol 3.cbz`, `Vol 4.cbr` → `Vol 4.cbz`).
Le doppie pagine vengono comunque tagliate e le informazioni del volume aggiunte; vanno bene anche i file senza numero nel nome.

```
python3 chapters2volumes.py "~/Manga/I Miei Volumi" --no-merge --dry-run
python3 chapters2volumes.py "~/Manga/I Miei Volumi" --no-merge -o "~/Manga/CBZ"
```

I tuoi file originali non vengono mai sovrascritti: se un CBZ avesse lo stesso nome di un CBZ originale nella stessa cartella,
il programma si rifiuta e ti chiede di scegliere un'altra cartella con `-o`.

## Tutte le opzioni

| Opzione | Cosa fa | Normalmente |
|---|---|---|
| *cartella* (primo argomento) | cartella con i capitoli (PDF, CBZ, CBR, cartelle di immagini o misti) | obbligatoria |
| `-o`, `--output` | dove salvare i volumi | `output` |
| `-s`, `--series` | nome della serie, usato nei nomi dei file e nelle informazioni del volume | il nome della cartella |
| `--dry-run` | solo anteprima, non crea niente | spento |
| `--detect` | come riconosce l'inizio di un volume: `color` o `colour` (copertina a colori), `portrait` (qualsiasi pagina singola verticale), `none` (a mano) | `color` |
| `--threshold X` | quanto deve essere colorata una pagina per essere una copertina (da 0 a 1) | 0.25 |
| `--min-chapters N` | numero minimo di capitoli per volume | 5 |
| `--max-chapters N` | numero massimo di capitoli per volume | nessun limite |
| `--starts 25,37` | capitoli che iniziano sicuramente un volume | nessuno |
| `--not-starts 42` | capitoli che sicuramente non iniziano un volume | nessuno |
| `--from N` / `--to N` | usa solo i capitoli dal numero N / fino al numero N | tutti |
| `--first-volume N` | numero del primo volume (es. per continuare una serie già convertita) | 1 |
| `--no-merge` | non unire: trasforma ogni file o cartella in un CBZ a sé, con lo stesso nome | spento |
| `--no-split` | non tagliare le doppie pagine | taglia |
| `--left-first` | prima la metà sinistra (lettura occidentale) | prima la destra |
| `--overwrite` | rifà e sostituisce i CBZ esistenti, anche se già fatti o creati da file che non ci sono più | li lascia com'erano |

`python3 chapters2volumes.py --help` mostra lo stesso elenco (in inglese).

## Buono a sapersi

- **Come vengono numerati i capitoli:** il programma usa l'**ultimo numero nel nome del file o della cartella**:
  `Il Mio Manga - Capitolo 012.pdf` → capitolo 12.
  Due numeri uniti da `.`, `_` o `-` vengono letti come **numero decimale**: `22.5`, `22_5` e `22-5` sono tutti 22,5,
  che va dopo il 22 e prima del 23. Come per ogni decimale, `22.10` vale 22,1, quindi viene **prima** di `22.2`
  (e `22.1` e `22.10` contano come lo stesso capitolo: se ci sono tutti e due ricevi un avviso).
  Lo stesso vale per le opzioni: `--starts 22_5`, `--from 22.5`.
  Evita altri numeri alla fine del nome (es. `Capitolo 12 (2024).pdf` verrebbe letto come capitolo 2024).
- **Cartelle di immagini:** ogni cartella dentro la cartella principale è un capitolo (es. `Il Mio Manga/Capitolo 12/001.jpg`).
  Le pagine vengono prese in ordine di nome, sottocartelle comprese; le cartelle senza immagini vengono ignorate.
- **Formati misti:** tutti i formati possono stare nella stessa cartella. Se lo stesso capitolo c'è in più formati,
  il programma usa il PDF, poi il CBZ, poi il CBR, poi la cartella, e ti avvisa.
- **Archivi con l'estensione "sbagliata":** molti file ".cbr" in realtà sono ZIP (e alcuni ".cbz" sono RAR).
  Il programma guarda cosa c'è dentro il file, non l'estensione, quindi funzionano lo stesso.
- **Dentro un CBZ o un CBR** le pagine vengono prese in ordine di nome (`pag2` viene prima di `pag10`); i file nascosti e di sistema vengono ignorati.
- **Gli archivi protetti da password** non si possono leggere: il programma ti dice quale capitolo è.
- **Nomi di serie** con caratteri che Windows non accetta nei nomi dei file (`: ? * " < > |`) vanno bene:
  quei caratteri diventano `-` nel nome del file, mentre il titolo vero resta nelle informazioni del volume.
- **Rilanciarlo** è sicuro e veloce: i volumi già fatti con gli stessi capitoli vengono saltati.
  Se aggiungi o sostituisci dei capitoli (o delle pagine in una cartella-capitolo), vengono rifatti solo i volumi che sono cambiati.
- **I tuoi volumi esistenti non vengono mai persi.** Un CBZ che c'è già nella cartella di uscita viene sostituito solo se
  si può ricreare senza perdere niente: è stato fatto da questo programma e tutti i file da cui è nato ci sono ancora.
  Altrimenti resta com'è, l'anteprima lo segna con `will NOT be replaced` e il programma ti dice cosa fare.
  `--overwrite` lo sostituisce comunque.
- **Nuovi capitoli più avanti?** Se hai ancora tutti i vecchi capitoli, aggiungi i nuovi e rilancia lo stesso comando:
  vengono rifatti solo i volumi che cambiano. Se i vecchi capitoli non ci sono più (hai tenuto solo i volumi), aggiungi
  i nuovi capitoli e lancia il comando: il programma lascia intatti i tuoi volumi e ti dice il numero da usare con
  `--first-volume`, così i nuovi volumi vengono dopo quelli vecchi.
- **Salvare i volumi nella stessa cartella dei capitoli** va bene: il programma riconosce i propri volumi e non li scambia mai per capitoli.
- **Limiti:** il taglio è sempre esattamente a metà dell'immagine; una pagina composta da più immagini dentro un PDF non viene ricomposta (ricevi un avviso).

## Messaggi principali e cosa fare

| Messaggio | Significa | Cosa fare |
|---|---|---|
| `WARNING: chapters missing from the numbering: [...]` | mancano dei capitoli | controlla se ti servono; il programma continua comunque |
| `Reading PDFs needs pdfimages` | manca poppler | installalo (vedi *Cosa serve*) |
| `... reading them needs bsdtar` | manca bsdtar (serve per i CBR) | installalo (vedi *Cosa serve*) |
| `ModuleNotFoundError: No module named 'PIL'` | manca Pillow | installalo (vedi *Cosa serve*) |
| `This program needs Python 3.8 or newer` | Python è troppo vecchio | installa un Python più recente |
| `The folder ... doesn't exist` | la cartella non esiste | controlla il percorso, e usa le virgolette se contiene spazi |
| `No chapters (PDF, CBZ, CBR or folders of images) found` | nessun capitolo trovato | nella cartella non ci sono file o cartelle-capitolo con un numero nel nome |
| `Tip: no volume start was found` | nessuna copertina trovata | probabilmente le copertine non sono a colori: vedi la [modalità manuale](#modalità-manuale-quando-non-ci-sono-copertine-a-colori) |
| `a page is not a readable image` | un capitolo è rovinato o protetto da password | sostituisci quel file |
| `Volumes NOT created: [...]` / `NOT converted: [...]` | alcuni file non sono stati creati | la riga con `ERROR` indica il file rovinato: sostituiscilo e rilancia lo stesso comando |
| `would replace your original file` | con `--no-merge`, il risultato sovrascriverebbe un tuo file | salva in un'altra cartella con `-o` |
| `KEPT` / `NOT replaced` | un CBZ con quel nome esiste già e non si può ricreare, quindi è stato lasciato com'era | segui il consiglio che compare (di solito `--first-volume N`), scegli un'altra cartella con `-o`, oppure usa `--overwrite` |

## Verificare che funzioni (facoltativo)

`test_chapters2volumes.py` crea finti capitoli (PDF, CBZ, veri file RAR e cartelle di immagini) in una cartella temporanea
e controlla volumi, ordine delle pagine, taglio, parti di capitolo, modalità manuale, `--no-merge`, gestione degli errori, sicurezza e altro:

```
python3 test_chapters2volumes.py
```

Finisce con `ALL CHECKS PASSED` e non lascia niente in giro. Richiede poppler e bsdtar, e funziona su Linux e macOS.

## Nota

Questo strumento serve a organizzare copie di opere **che hai il diritto di possedere e leggere**. Non contiene manga e non scarica niente.

## Licenza

[MIT](LICENSE): puoi usarlo, copiarlo, modificarlo e condividerlo liberamente, basta mantenere l'indicazione dell'autore.

"""
Make the figures for docs/how_the_tally_works.md.

Renders one measure of a WTC score, its chordified version, and one slice
taken apart into note pairs, as PNG files in docs/img/.
Requires MuseScore 4 for the rendering; set the environment variable MSCORE
if it is not installed in the default macOS location.

Usage (from the repository root):
    python docs/make_tally_figures.py
"""

import music21 as m21, subprocess, glob, os, sys, tempfile
from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from temperament_functions import get_semitone_interval

# The example: Book I, prelude in E-flat major, measure 14, slice 3
SCORE = os.path.join(ROOT, 'scores_xml', 'BWV_0852.xml')
MN = 14
SLICE = 3
ks = m21.key.KeySignature(-3)

TMP = tempfile.mkdtemp() + '/'
OUT = os.path.join(ROOT, 'docs', 'img') + '/'
MS = os.environ.get('MSCORE', '/Applications/MuseScore 4.app/Contents/MacOS/mscore')

IVS = ["P1", "m2", "M2", "m3", "M3", "P4", "A4-d5", "P5", "m6", "M6", "m7", "M7"]

def clean(sc):
    sc.metadata = m21.metadata.Metadata()
    sc.metadata.title = ''
    sc.metadata.composer = ''
    for p in sc.parts:
        p.partName = ''
        p.partAbbreviation = ''
    return sc

def fix_accidentals(stream, ks):
    # Hide accidentals that are already in the key signature
    # (all accidentals in this excerpt are diatonic flats).
    in_key = {p.name for p in ks.alteredPitches}
    for n in stream.recurse().notes:
        for p in n.pitches:
            if p.accidental is not None:
                p.accidental.displayStatus = p.name not in in_key

def render(sc, name):
    xml = TMP + name + '.musicxml'
    sc.write('musicxml', xml)
    for f in glob.glob(TMP + name + '-*.png'):
        os.remove(f)
    # No check=True: mscore sometimes crashes on exit after writing the PNG.
    # MuseScore writes one file per page (name-1.png, ...); we need page 1.
    subprocess.run([MS, '-r', '220', '-o', TMP + name + '.png', xml])
    img = Image.open(TMP + name + '-1.png').convert('RGBA')
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(bg, img).convert('RGB')
    diff = ImageChops.difference(flat, Image.new('RGB', flat.size, (255, 255, 255)))
    # Crop away the empty part of the page
    l, t, r, b = diff.getbbox()
    pad = 30
    flat.crop((l - pad, t - pad, r + pad, b + pad)).save(OUT + name + '.png')

s = m21.converter.parse(SCORE)

# 1) The original measure
render(clean(s.measures(MN, MN)), 'tally_1_measure')

# 2) The chordified measure, slices numbered
c = s.chordify(removeRedundantPitches=False).measures(MN, MN)
chords = list(c.recurse().getElementsByClass('Chord'))
for i, ch in enumerate(chords, 1):
    ch.addLyric(str(i))
fix_accidentals(c, ks)
cs = m21.stream.Score()
cs.insert(0, c)
render(clean(cs), 'tally_2_chordified')

# 3) Slice 3 taken apart into its note pairs
ch = chords[SLICE - 1]
w = float(ch.quarterLength) * ch.beatStrength
part = m21.stream.Part()
m1 = m21.stream.Measure(number=1)
m1.append(m21.clef.TrebleClef())
m1.append(ks)
ts1 = m21.meter.TimeSignature('1/1')
ts1.style.hideObjectOnPrint = True
m1.append(ts1)
whole = m21.chord.Chord([m21.note.Note(n.pitch) for n in ch.notes], quarterLength=4)
whole.addLyric(f'slice {SLICE}')
m1.append(whole)
m1.rightBarline = m21.bar.Barline('double')
m2 = m21.stream.Measure(number=2)
pairs = []
notes = list(ch.notes)
for i in range(len(notes)):
    for j in range(i + 1, len(notes)):
        pairs.append((notes[i], notes[j]))
ts2 = m21.meter.TimeSignature(f'{len(pairs)}/2')
ts2.style.hideObjectOnPrint = True
m2.append(ts2)
for a, b in pairs:
    iv, lo, hi = get_semitone_interval(a, b)
    d = m21.chord.Chord([m21.note.Note(a.pitch), m21.note.Note(b.pitch)], quarterLength=2)
    d.addLyric(IVS[iv])
    d.addLyric(f'({lo}, {hi}, {iv})')
    d.addLyric(f'+{w:g}')
    m2.append(d)
    print(f'{a.nameWithOctave}-{b.nameWithOctave}', IVS[iv], (lo, hi, iv), w)
m2.rightBarline = m21.bar.Barline('final')
part.append([m1, m2])
fix_accidentals(part, ks)
ps = m21.stream.Score()
ps.insert(0, part)
render(clean(ps), 'tally_3_pairs')

# Print the slices (for the table in the markdown file)
for i, ch in enumerate(chords, 1):
    print(i, ch.offset, float(ch.quarterLength), ch.beatStrength, [n.nameWithOctave for n in ch.notes])

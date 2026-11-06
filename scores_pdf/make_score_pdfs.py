"""
Make a PDF of every MusicXML file in scores_xml/, with a bar number at every bar.

The bar numbers are the ones music21 gives (Measure.number), so that a bar
number from the analysis, e.g. score.measures(14, 14), can be looked up
directly in the PDF.

Requires MuseScore 4; set the environment variable MSCORE if it is not
installed in the default macOS location.

Usage (from the repository root):
    python scores_pdf/make_score_pdfs.py            # all files
    python scores_pdf/make_score_pdfs.py BWV_0846   # only some files
"""

import glob, os, re, subprocess, sys, tempfile
import music21 as m21

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XML_DIR = os.path.join(ROOT, 'scores_xml')
OUT_DIR = os.path.join(ROOT, 'scores_pdf')
MS = os.environ.get('MSCORE', '/Applications/MuseScore 4.app/Contents/MacOS/mscore')

# Printed at the foot of the first page (required by the licence of the
# MusicXML files, see scores_xml/LICENSE).
SOURCE_NOTICE = ('Quelle: www.tobis-notenarchiv.de (Tobias Schölkopf), corrected version. '
                 'Licence: CC BY-NC-SA 4.0')

# Engraving style: show the bar number at every bar, also at the first bar.
STYLE = """<?xml version="1.0" encoding="UTF-8"?>
<museScore version="4.20">
  <Style>
    <showMeasureNumber>1</showMeasureNumber>
    <showMeasureNumberOne>1</showMeasureNumberOne>
    <measureNumberInterval>1</measureNumberInterval>
    <measureNumberSystem>0</measureNumberSystem>
  </Style>
</museScore>
"""


def note_to_forward(note):
    """Replace a <note> element by a <forward> of the same length (an invisible gap)."""
    g = lambda t: re.search(r'<%s>(.*?)</%s>' % (t, t), note, re.S).group(1)
    return '<forward><duration>%s</duration><voice>%s</voice><staff>%s</staff></forward>' % (
        g('duration'), g('voice'), g('staff'))


def fix_874(xml):
    # MuseScore 4 crashes on the triplets in m. 28. Leaving out one triplet
    # sixteenth rest in voice 2 avoids that. Rests are not part of the analysis.
    def fix(m):
        notes = list(re.finditer(r'<note[ >].*?</note>', m.group(0), re.S))
        n = notes[25]
        assert '<voice>2</voice>' in n.group(0) and '<rest/>' in n.group(0)
        return m.group(0)[:n.start()] + note_to_forward(n.group(0)) + m.group(0)[n.end():]
    return re.sub(r'<measure number="28".*?</measure>', fix, xml, count=1, flags=re.S)


def fix_880(xml):
    # MuseScore 4 crashes (later on, at m. 124) because of the invisible rests
    # in m. 28. Replacing them by invisible gaps changes nothing in the print.
    def fix(m):
        return re.sub(r'<note print-object="no">.*?</note>',
                      lambda n: note_to_forward(n.group(0)) if '<rest/>' in n.group(0) else n.group(0),
                      m.group(0), flags=re.S)
    return re.sub(r'<measure number="28".*?</measure>', fix, xml, count=1, flags=re.S)


FIXES = {'BWV_0874': fix_874, 'BWV_0880': fix_880}


def take_headings(xml):
    """Remove the title texts from the music and return them separately.

    The files have the title, the subtitle and the composer as text attached
    to the first bar, with fixed positions that MuseScore places badly. They
    are put in a title frame instead (see set_headings). The headings
    '1. Präludium' and '2. Fuga ...' stay where they are, but without their
    fixed positions.
    """
    headings = {'title': '', 'subtitle': '', 'composer': ''}

    def classify(direction):
        w = re.search(r'<words([^>]*)>([^<]*)</words>', direction)
        if not w:
            return None
        text = w.group(2).strip()
        if text.startswith('Präludium und Fuge'):
            return 'title', text
        if text.startswith('Aus dem wohltemperierten'):
            return 'subtitle', text
        if text.startswith('Johann Sebastian Bach'):
            return 'composer', text
        return None

    def take(m):
        c = classify(m.group(0))
        if c is None:
            return m.group(0)
        headings[c[0]] = c[1]
        return ''

    xml = re.sub(r'<direction[ >](?:(?!</direction>).)*</direction>', take, xml, flags=re.S)
    xml = re.sub(r'<credit[ >].*?</credit>', '', xml, flags=re.S)
    xml = re.sub(r'<words[^>]*>',
                 lambda m: re.sub(r'\s(relative-x|default-y)="[^"]*"', '', m.group(0)), xml)
    return xml, headings


def set_bar_numbers(xml, numbers):
    """Give the measures the bar numbers that music21 uses (one per measure).

    MuseScore takes the bar numbers from the measures' number attributes, but
    numbers a measure such as '28A' as 29. Without the suffix it shows 28.
    """
    measures = iter(numbers)
    xml = re.sub(r'<measure number="[^"]*"',
                 lambda m: '<measure number="%d"' % next(measures), xml)
    assert next(measures, None) is None
    return xml


def set_headings(xml, headings):
    """Put the title, subtitle, composer and source notice in the file header.

    MuseScore makes a title frame from them, and prints the source notice
    at the foot of the first page.
    """
    esc = lambda t: t.replace('&', '&amp;').replace('<', '&lt;')
    # Positions in tenths on the page as defined in the files (1312 x 1856)
    look = {'title': 'default-x="656" default-y="1763" justify="center" valign="top" font-size="20"',
            'subtitle': 'default-x="656" default-y="1710" justify="center" valign="top" font-size="12"',
            'composer': 'default-x="1219" default-y="1670" justify="right" valign="top" font-size="10"',
            'rights': 'default-x="656" default-y="60" justify="center" valign="bottom" font-size="8"'}
    texts = dict(headings, rights=SOURCE_NOTICE)
    credits = ''.join('<credit page="1"><credit-type>%s</credit-type>'
                      '<credit-words %s>%s</credit-words></credit>'
                      % (kind, look[kind], esc(text))
                      for kind, text in texts.items() if text)
    return xml.replace('<part-list>', credits + '<part-list>', 1)


def make_pdf(xml_path, tmp):
    name = os.path.basename(xml_path)[:-4]
    # Bar numbers as music21 sees them
    score = m21.converter.parse(xml_path)
    numbers = [m.number for m in score.parts[0].getElementsByClass('Measure')]

    # Prepare a copy of the MusicXML file for MuseScore
    xml = open(xml_path, encoding='utf-8').read()
    if name in FIXES:
        xml = FIXES[name](xml)
    xml, headings = take_headings(xml)
    bwv = name.replace('_0', ' ').replace('_', ' ')   # BWV_0846 -> BWV 846
    headings['title'] = headings['title'] or bwv
    headings['composer'] = headings['composer'] or 'Johann Sebastian Bach\n' + bwv
    xml = set_headings(set_bar_numbers(xml, numbers), headings)
    src = os.path.join(tmp, name + '.xml')
    open(src, 'w', encoding='utf-8').write(xml)

    # MusicXML -> PDF
    pdf = os.path.join(OUT_DIR, name + '.pdf')
    if os.path.exists(pdf):
        os.remove(pdf)
    style = os.path.join(tmp, 'bar_numbers.mss')
    open(style, 'w').write(STYLE)
    # No check=True: mscore sometimes crashes on exit after writing the file.
    subprocess.run([MS, '-S', style, '-o', pdf, src], capture_output=True)
    if not os.path.exists(pdf):
        raise RuntimeError('MuseScore could not convert ' + xml_path)
    print(pdf)


if __name__ == '__main__':
    names = sys.argv[1:]
    files = sorted(glob.glob(os.path.join(XML_DIR, '*.xml')))
    if names:
        files = [f for f in files if os.path.basename(f)[:-4] in names]
    with tempfile.TemporaryDirectory() as tmp:
        for f in files:
            make_pdf(f, tmp)

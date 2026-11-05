"""
Functions for tallying harmonic interval occurrences in a corpus of scores
(here: Bach's Well-Tempered Clavier, BWV 846-893).

Every interval is stored as a key of the form

    (lower_pitch_class, upper_pitch_class, interval_class)

where pitch classes are integers 0-11 (C=0, C#/Db=1, ..., B=11) and the
interval class is the number of semitones from the lower to the upper note,
reduced modulo 12 (0 = unison/octave, 4 = major third, 7 = perfect fifth, ...).
Note spelling is discarded: D#-F# and Eb-Gb both become (3, 6, 3).
The value stored under each key is an accumulated (weighted) count.
"""

import music21 as m21
from collections import defaultdict, deque

def get_semitone_interval(note1, note2):
    """Return (interval_class, lower_pitch_class, upper_pitch_class) for two notes.

    The interval is measured from the lower to the higher note and reduced
    modulo 12, so compound intervals are folded into one octave
    (e.g. a tenth counts as a major/minor third, an octave counts as 0).
    """
    # MIDI numbers identify the sounding key on the keyboard (C4 = 60),
    # so enharmonic spellings (D#4, Eb4) give the same number.
    pitch1 = note1.pitch.midi
    pitch2 = note2.pitch.midi
    lowest_pitch = min([pitch1, pitch2])
    highest_pitch = max([pitch1, pitch2])
    raw_interval = (highest_pitch - lowest_pitch) % 12
    return raw_interval, lowest_pitch % 12, highest_pitch % 12

def analyze_intervals(
        score,
        pair_frequencies,
        durationWeight=True,
        metricWeight=True,
    ):
    """Add the harmonic intervals found in `score` to `pair_frequencies` (modified in place).

    Only simultaneous intervals (between notes sounding together) are counted,
    not intervals between successive notes.

    score            -- a music21 Score
    pair_frequencies -- dict mapping (low_pc, high_pc, interval) -> weight;
                        should be a defaultdict(float)
    durationWeight   -- if True, weight each occurrence by its duration
                        in quarter notes; otherwise each occurrence counts 1
    metricWeight     -- if True, also multiply by music21's beatStrength
                        (1.0 on the downbeat, smaller on weaker beats)
    """
    # chordify() merges all parts into a single sequence of chords.
    # A new chord ("slice") starts whenever any note starts or stops,
    # so a note held while other voices move is split over several slices.
    # By default chordify() would also remove duplicate pitches within a slice
    # (two voices on the very same note would become one note). We keep them,
    # so that true unisons between voices are counted as P1.
    chordified = score.chordify(removeRedundantPitches=False)
    for chord in chordified.recurse().getElementsByClass('Chord'):
        notes = chord.notes
        # Count every pair of notes in the slice: a slice with k notes
        # contributes k*(k-1)/2 intervals.
        for i in range(len(notes)):
            for j in range(i + 1, len(notes)):
                if notes[i].isNote and notes[j].isNote:
                    interval, pitch1, pitch2 = get_semitone_interval(notes[i], notes[j])
                    # Weight = how long the slice lasts ...
                    if durationWeight:
                        w_dur = chord.quarterLength
                    else:
                        w_dur = 1.0
                    # ... times how strong the metric position of the slice is.
                    if metricWeight:
                        w_met = chord.beatStrength
                    else:
                        w_met = 1.0
                    pair_frequencies[(pitch1, pitch2, interval)] += (w_met * w_dur)


def process_scores(score_files, durationWeight=True, metricWeight=True, total_weight=None):
    """Parse all `score_files` and return the combined interval tally.

    The returned defaultdict contains only intervals that actually occur
    (intervals that never occur are missing, not present with value 0).

    total_weight -- if given, all values are scaled so that they sum to this
                    number; with total_weight=1.0 each value is the share
                    of that interval in the whole corpus.
    The other keyword arguments are passed on to analyze_intervals().
    """
    pair_frequencies = defaultdict(float)
    for filepath in score_files:
        score = m21.converter.parse(filepath)
        # All scores add to the same dict, so the result is a tally over
        # the whole corpus, not an average over pieces.
        analyze_intervals(
            score,
            pair_frequencies,
            durationWeight=durationWeight,
            metricWeight=metricWeight,
        )
    # Normalize
    if total_weight != None:
        sum_of_weights = sum(pair_frequencies.values())
        normlization_factor = total_weight / sum_of_weights
        for k in pair_frequencies.keys():
            pair_frequencies[k] = pair_frequencies[k] * normlization_factor

    return pair_frequencies

def pprint_interval_data(pair_frequencies, number_of_flats=3):
    """Print the tally three times: grouped by interval, by lower note, and by weight.

    Because the tally only stores pitch classes (0-11), a spelling has to be
    chosen for printing. `number_of_flats` sets how many of the five black
    keys are spelled as flats (negative values: more sharps, e.g. E#, B#).
    The default 3 gives C C# D Eb E F F# G Ab A Bb B.
    The spelling is for display only: it says nothing about how the note
    was written in the score.
    """

    # Resulting spellings for pitch classes 0-11 for each number_of_flats:
    # -6 ['B#', 'C#', 'C##', 'D#', 'D##', 'E#', 'F#', 'F##', 'G#', 'G##', 'A#', 'B']
    # -5 ['B#', 'C#', 'C##', 'D#', 'E', 'E#', 'F#', 'F##', 'G#', 'G##', 'A#', 'B']
    # -4 ['B#', 'C#', 'C##', 'D#', 'E', 'E#', 'F#', 'F##', 'G#', 'A', 'A#', 'B']
    # -3 ['B#', 'C#', 'D', 'D#', 'E', 'E#', 'F#', 'F##', 'G#', 'A', 'A#', 'B']
    # -2 ['B#', 'C#', 'D', 'D#', 'E', 'E#', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    # -1 ['C', 'C#', 'D', 'D#', 'E', 'E#', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    # 0 ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    # 1 ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B']
    # 2 ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B']
    # 3 ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
    # 4 ['C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
    # 5 ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    # 6 ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'Cb']
    # 7 ['C', 'Db', 'D', 'Eb', 'Fb', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'Cb']
    # 8 ['C', 'Db', 'D', 'Eb', 'Fb', 'F', 'Gb', 'G', 'Ab', 'Bbb', 'Bb', 'Cb']
    # 9 ['C', 'Db', 'Ebb', 'Eb', 'Fb', 'F', 'Gb', 'G', 'Ab', 'Bbb', 'Bb', 'Cb']
    # 10 ['C', 'Db', 'Ebb', 'Eb', 'Fb', 'F', 'Gb', 'Abb', 'Ab', 'Bbb', 'Bb', 'Cb']
    # 11 ['Dbb', 'Db', 'Ebb', 'Eb', 'Fb', 'F', 'Gb', 'Abb', 'Ab', 'Bbb', 'Bb', 'Cb']
    # 12 ['Dbb', 'Db', 'Ebb', 'Eb', 'Fb', 'Gbb', 'Gb', 'Abb', 'Ab', 'Bbb', 'Bb', 'Cb']

    # Note names in "line of fifths" order: each name is a perfect fifth
    # above the previous one. Index 14 is F, index 15 is C.
    allpitches = ["Fbb", "Cbb", "Gbb", "Dbb", "Abb", "Ebb", "Bbb",
                  "Fb", "Cb", "Gb", "Db", "Ab", "Eb", "Bb",
                  "F", "C", "G", "D", "A", "E", "B",
                  "F#", "C#", "G#", "D#", "A#", "E#", "B#",
                  "F##", "C##", "G##", "D##", "A##", "E##", "B##"]
    # Take a window of 12 consecutive fifths (one name per pitch class).
    # Shifting the window left by one fifth swaps one sharp for a flat.
    pitches_subset = deque(allpitches[14-number_of_flats:26-number_of_flats])
    # Rotate so that the window starts at the name for pitch class 0 (C or its enharmonic).
    pitches_subset.rotate(-number_of_flats-1)
    # Element k of the window is k fifths above C, i.e. pitch class 7*k mod 12.
    # This list gives, for pitch classes 0..11, their position in the window
    # (pitch class p sits at position 7*p mod 12).
    pitches = {ix: pitches_subset[pitch_ix] for ix, pitch_ix in enumerate([0,7,2,9,4,11,6,1,8,3,10,5])}
    # Names for the interval classes. 0 includes unisons and octaves (intervals are reduced mod 12).
    intervals = { 0: "P1", 1: "m2", 2: "M2", 3: "m3", 4: "M3", 5: "P4", 6: "A4-d5", 7: "P5", 8: "m6", 9: "M6", 10: "m7", 11: "M7" }

    # Each item is ((low_pc, high_pc, interval), weight); iv[0] is the key, iv[1] the weight.

    # 1) Grouped by interval class, highest weight first within each group.
    print("Sorted by interval")
    p_iv = -1
    for iv in sorted(list(pair_frequencies.items()), key=lambda x: (x[0][2], -x[1])):
        interval = iv[0][2]
        if interval != p_iv:
            print(f"--- {intervals[interval]} ---")
            p_iv = interval
        print(f"{pitches[iv[0][0]]:<2} - {pitches[iv[0][1]]:<2} : {iv[1]:.4f}")

    # 2) Grouped by the lower note of the interval.
    print()
    print("Sorted by root note")
    for iv in sorted(list(pair_frequencies.items()), key=lambda x: (x[0][0], -x[1])):
        print(f"{pitches[iv[0][0]]:<2} - {pitches[iv[0][1]]:<2} : {iv[1]:.4f}")

    # 3) All intervals, highest weight first.
    print()
    print("Sorted by weight")
    for iv in sorted(list(pair_frequencies.items()), key=lambda x: -x[1]):
        print(f"{pitches[iv[0][0]]:<2} - {pitches[iv[0][1]]:<2} : {iv[1]:.4f}")

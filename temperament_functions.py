import music21 as m21
from collections import defaultdict, deque

def get_semitone_interval(note1, note2):
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
        harmonic=True,
        melodic=True,
    ):
    if harmonic:
        chordified = score.chordify()
        for chord in chordified.recurse().getElementsByClass('Chord'):
            notes = chord.notes
            for i in range(len(notes)):
                for j in range(i + 1, len(notes)):
                    if notes[i].isNote and notes[j].isNote:
                        interval, pitch1, pitch2 = get_semitone_interval(notes[i], notes[j])
                        if durationWeight:
                            w_dur = chord.quarterLength
                        else:
                            w_dur = 1.0
                        if metricWeight:
                            w_met = chord.beatStrength
                        else:
                            w_met = 1.0
                        pair_frequencies[(pitch1, pitch2, interval)] += (w_met * w_dur)
    if melodic:
        for part in score.parts:
            notes = [n for n in part.flatten().notes if n.isNote]
            for i in range(len(notes) - 1):
                interval, pitch1, pitch2 = get_semitone_interval(notes[i], notes[i + 1])
                if durationWeight:
                    w_dur = min(notes[i].quarterLength, notes[i+1].quarterLength)
                else:
                    w_dur = 1.0
                if metricWeight:
                    w_met = notes[i + 1].beatStrength
                else:
                    w_met = 1.0
                pair_frequencies[(pitch1, pitch2, interval)] += (w_met * w_dur)


# Output contains all possible intervals.
def process_scores(score_files, durationWeight=True, metricWeight=True, total_weight=None, harmonic=True, melodic=True):
    pair_frequencies = defaultdict(float)
    for filepath in score_files:
        score = m21.converter.parse(filepath)
        analyze_intervals(
            score,
            pair_frequencies,
            durationWeight=durationWeight,
            metricWeight=metricWeight,
            harmonic=harmonic,
            melodic=melodic,
        )
    # Normalize
    if total_weight != None:
        sum_of_weights = sum(pair_frequencies.values())
        normlization_factor = total_weight / sum_of_weights
        for k in pair_frequencies.keys():
            pair_frequencies[k] = pair_frequencies[k] * normlization_factor

    return pair_frequencies

def pprint_interval_data(pair_frequencies, number_of_flats=3):

    # Pitch spellings for number_of_flats:
    # -6 ['B#', 'C#', 'C##', 'D#', 'D##', 'E#', 'F#', 'F##', 'G#', 'G##', 'A#']
    # -5 ['B#', 'C#', 'C##', 'D#', 'E', 'E#', 'F#', 'F##', 'G#', 'G##', 'A#']
    # -4 ['B#', 'C#', 'C##', 'D#', 'E', 'E#', 'F#', 'F##', 'G#', 'A', 'A#']
    # -3 ['B#', 'C#', 'D', 'D#', 'E', 'E#', 'F#', 'F##', 'G#', 'A', 'A#']
    # -2 ['B#', 'C#', 'D', 'D#', 'E', 'E#', 'F#', 'G', 'G#', 'A', 'A#']
    # -1 ['C', 'C#', 'D', 'D#', 'E', 'E#', 'F#', 'G', 'G#', 'A', 'A#']
    # 0 ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#']
    # 1 ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb']
    # 2 ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb']
    # 3 ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb']
    # 4 ['C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb']
    # 5 ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb']
    # 6 ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb']
    # 7 ['C', 'Db', 'D', 'Eb', 'Fb', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb']
    # 8 ['C', 'Db', 'D', 'Eb', 'Fb', 'F', 'Gb', 'G', 'Ab', 'Bbb', 'Bb']
    # 9 ['C', 'Db', 'Ebb', 'Eb', 'Fb', 'F', 'Gb', 'G', 'Ab', 'Bbb', 'Bb']
    # 10 ['C', 'Db', 'Ebb', 'Eb', 'Fb', 'F', 'Gb', 'Abb', 'Ab', 'Bbb', 'Bb']
    # 11 ['Dbb', 'Db', 'Ebb', 'Eb', 'Fb', 'F', 'Gb', 'Abb', 'Ab', 'Bbb', 'Bb']
    # 12 ['Dbb', 'Db', 'Ebb', 'Eb', 'Fb', 'Gbb', 'Gb', 'Abb', 'Ab', 'Bbb', 'Bb']

    allpitches = ["Fbb", "Cbb", "Gbb", "Dbb", "Abb", "Ebb", "Bbb",
                  "Fb", "Cb", "Gb", "Db", "Ab", "Eb", "Bb", 
                  "F", "C", "G", "D", "A", "E", "B",
                  "F#", "C#", "G#", "D#", "A#", "E#", "B#",
                  "F##", "C##", "G##", "D##", "A##", "E##", "B##"]
    pitches_subset = deque(allpitches[14-number_of_flats:26-number_of_flats])
    pitches_subset.rotate(-number_of_flats-1)
    pitches = {ix: pitches_subset[pitch_ix] for ix, pitch_ix in enumerate([0,7,2,9,4,11,6,1,8,3,10,5])}
    intervals = { 0: "P1", 1: "m2", 2: "M2", 3: "m3", 4: "M3", 5: "P4", 6: "A4-d5", 7: "P5", 8: "m6", 9: "M6", 10: "m7", 11: "M7" }

    print("Sorted by interval")
    p_iv = -1
    for iv in sorted(list(pair_frequencies.items()), key=lambda x: (x[0][2], -x[1])):
        interval = iv[0][2]
        if interval != p_iv:
            print(f"--- {intervals[interval]} ---")
            p_iv = interval
        print(f"{pitches[iv[0][0]]:<2} - {pitches[iv[0][1]]:<2} : {iv[1]:.4f}")

    print()
    print("Sorted by root note")
    for iv in sorted(list(pair_frequencies.items()), key=lambda x: (x[0][0], -x[1])):
        print(f"{pitches[iv[0][0]]:<2} - {pitches[iv[0][1]]:<2} : {iv[1]:.4f}")

    print()
    print("Sorted by weight")
    for iv in sorted(list(pair_frequencies.items()), key=lambda x: -x[1]):
        print(f"{pitches[iv[0][0]]:<2} - {pitches[iv[0][1]]:<2} : {iv[1]:.4f}")




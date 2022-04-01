# Load and process a corpus into trigram frequencies, subject to certain settings
# Members:
    # raw: raw text of the corpus, directly from a file
    # processed: a list of 1-grams? may not be necessary
    # shift_rule: enum of lshift, rshift, lowercase, and possibly opposite shift
    # space_rule: enum of lspace, rspace, nospace, and possibly opposite space
    # key_counts: dict[str, int]
    # bigram_counts: dict[Bigram, int]
    # trigram_counts: dict[Trigram, int]
    # trigrams_by_freq: list[Trigram]
    # trigram_precision: int
    # trigram_completeness: float
    # replacements: dict[str, tuple[str, ...]]

from enum import Enum, auto

Bigram = tuple[str, str]
Trigram = tuple[str, str, str]

class KeyRule(Enum):
    LEFT = auto()
    RIGHT = auto()
    NONE = auto()

class Corpus:

    def __init__(self, filename: str, space_rule: KeyRule, 
                 shift_rule: KeyRule, 
                 replacements: dict[str, tuple[str,...]],
                 precision: int = 500) -> None:
        self.filename = filename
        self.space_rule = space_rule
        self.shift_rule = shift_rule
        self.replacements = replacements
        self.precision = precision

        with open("corpus/" + filename) as file:
            raw = file.read()

        self.processed = []

        for char in raw:
            self.processed.extend(replacements.get(char, (char,)))


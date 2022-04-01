# Load and process a corpus into trigram frequencies, subject to certain settings
# Members:
    # raw: raw text of the corpus, directly from a file
    # processed: a list of 1-grams? may not be necessary
    # shift_rule: enum of lshift, rshift, lowercase, and possibly opposite shift
    # space_rule: enum of lspace, rspace, nospace, and possibly opposite space
    # key_counts: dict[str, int]
    # bigram_counts: dict[Bigram, int]
    # trigram_counts: dict[Trigram, int]
    # trigrams_by_freq: list[Trigram] - possibly just use trigram_counts.most_common()
    # trigram_precision: int
    # trigram_completeness: float
    # replacements: dict[str, tuple[str, ...]]

from enum import Enum, auto
import collections
import itertools

Bigram = tuple[str, str]
Trigram = tuple[str, str, str]

class Rule(Enum):
    LEFT = auto()
    RIGHT = auto()
    NONE = auto()

class Corpus:

    default_lower = """`1234567890-=qwertyuiop[]\asdfghjkl;'zxcvbnm,./"""
    default_upper = """~!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:"ZXCVBNM<>?"""

    def __init__(self, filename: str, space_rule: Rule, 
                 shift_rule: Rule, 
                 special_replacements: dict[str, tuple[str,...]],
                 precision: int = 500) -> None:
        self.filename = filename
        self.space_rule = space_rule
        self.shift_rule = shift_rule
        self.special_replacements = special_replacements
        self.replacements = {" ": "space"}

        if shift_rule == Rule.NONE:
            for l, u in zip(self.default_lower, self.default_upper):
                self.replacements[u] = (l,)
        else:
            shift_key = "shift_r" if self.shift_rule == Rule.RIGHT else "shift"
            for l, u in zip(self.default_lower, self.default_upper):
                self.replacements[u] = (shift_key, l)

        self.replacements.update(special_replacements)

        with open("corpus/" + filename) as file:
            raw = file.read()
        self.processed = []
        legal_chars = (set(self.default_lower) | set(self.default_upper) 
            | set(self.replacements))
        for char in raw:
            if char in legal_chars:
                self.processed.extend(special_replacements.get(char, (char,)))

        self.key_counts = collections.Counter(self.processed)
        self.bigram_counts = collections.Counter(itertools.pairwise(self.processed))
        self.trigram_counts = collections.Counter(tuple(self.processed[i:i+3])
            for i in range(len(self.processed)-2))

        self.set_precision(precision)
        
    def set_precision(self, precision: int):
        self.precision = precision
        self.trigrams_by_freq = tuple(
            item[0] for item in 
                self.trigram_counts.most_common(self.precision))
        self.trigram_precision_total = sum(self.trigram_counts[tg] 
            for tg in self.trigrams_by_freq)
        self.trigram_completeness = (self.trigram_precision_total / 
            self.trigram_counts.total())

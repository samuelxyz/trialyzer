# Load and process a corpus into trigram frequencies, subject to certain settings
# Members:
    # shift_key: str
    # space_key: str
    # key_counts: dict[str, int]
    # bigram_counts: dict[Bigram, int]
    # trigram_counts: dict[Trigram, int]
    # trigrams_by_freq: list[Trigram] - possibly just use trigram_counts.most_common()
    # precision: int
    # trigram_completeness: float
    # replacements: dict[str, tuple[str, ...]]
    # special_replacements: dict[str, tuple[str, ...]]
# Local vars
    # raw: raw text of the corpus, directly from a file
    # processed: a list of 1-grams? may not be necessary

from collections import Counter
import itertools
import json
from typing import Type

Bigram = tuple[str, str]
Trigram = tuple[str, str, str]

default_lower = """`1234567890-=qwertyuiop[]\\asdfghjkl;'zxcvbnm,./"""
default_upper = """~!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:"ZXCVBNM<>?"""

def display_name(key: str, corpus_settings: dict):
    if key == corpus_settings.get("space_key", None):
        return "space"
    elif key == corpus_settings.get("shift_key", None):
        return "shift"
    elif key == corpus_settings.get("repeat_key", None):
        return "repeat"
    else:
        return key

def display_str(ngram: tuple[str, ...], corpus_settings: dict):
    return " ".join(display_name(key, corpus_settings) for key in ngram)

def undisplay_name(key: str, corpus_settings: dict):
    if key == "space":
        return corpus_settings.get("space_key", key)
    elif key == "shift":
        return corpus_settings.get("shift_key", key)
    elif key == "repeat":
        return corpus_settings.get("repeat_key", key)
    else:
        return key

def create_replacements(space_key: str, shift_key: str, 
        special_replacements: dict[str, tuple[str,...]]):
    """A dict from direct corpus characters to key sequences. 
    For example, "A" becomes the shift key and "a".
    """
    if space_key:
        replacements = {" ": (space_key,)}
    else:
        replacements = {" ": ()}

    if shift_key:
        for l, u in zip(default_lower, default_upper):
            replacements[u] = (shift_key, l)
    else:
        for l, u in zip(default_lower, default_upper):
            replacements[u] = (l,)

    replacements.update(special_replacements)
    legal_chars = (set(default_lower) | set(default_upper) 
        | set(replacements))
    for char in legal_chars:
        if char not in replacements:
            replacements[char] = (char,)

    return replacements

class TranslationError(ValueError):
    """Attempted to translate two corpuses that are not compatible."""

class Corpus:

    def __init__(self, filename: str, 
                 space_key: str = "space", 
                 shift_key: str = "shift", 
                 shift_policy: str = "once",
                 special_replacements: dict[str, tuple[str,...]] = {},
                 precision: int = 500, 
                 repeat_key: str = "",
                 json_dict: dict = None, 
                 other: Type["Corpus"] = None,
                 skipgram_weights: tuple[float] = None) -> None:
        """To disable a key, set it to `""`.

        `shift_policy` can be "once" or "each". "once" means that when 
        consecutive capital letters occur, shift is only pressed once before 
        the first letter. "each" means shift is pressed before each letter.
        
        `skipgram_weights` contains the weight in its `i`th index for pairs
        of the form `pos, pos+i` for any position in the corpus. For 
        example, regular bigrams would be weighted by the number at index 1.
        """
        self.filename = filename
        self.space_key = space_key
        self.shift_key = shift_key
        self.shift_policy = shift_policy
        self.special_replacements = special_replacements
        self.repeat_key = repeat_key
        self.skipgram_weights = skipgram_weights

        # Not necessarily integer, due to skipgram_weights floats
        self.skipgram_counts: Counter[tuple[str], float] = None

        if json_dict is not None:
            self._json_load(json_dict)
        elif other is not None:
            self._translate(other)
        else:
            self._process()
        self.precision = precision
        self.top_trigrams = ()
        self.trigram_precision_total = 0
        self.trigram_completeness = 0
        self.all_trigrams = tuple(
            item[0] for item in self.trigram_counts.most_common())
        self.set_precision(precision)

    def _process(self):
        self.replacements = create_replacements(
            self.space_key, self.shift_key, self.special_replacements
        )
        replacee_lengths = sorted(set(
            len(key) for key in self.replacements), reverse=True)

        self.key_counts = Counter()
        self.bigram_counts = Counter()
        self.skip1_counts = Counter()
        self.trigram_counts = Counter()

        if self.skipgram_weights:
            self.skipgram_counts = Counter()

        with open("corpus/" + self.filename, errors="ignore") as file:
            for raw_line in file:
                processed = []

                line_length = len(raw_line)
                i = 0
                while i < line_length:
                    for lookahead in replacee_lengths: # longest first
                        if i + lookahead <= line_length:
                            if (replacer := self.replacements.get(
                                    raw_line[i:i+lookahead], None)) is not None:
                                processed.extend(replacer)
                                i += lookahead
                                break
                    # if we get here, the character is not in corpus
                    # just skip the char and continue
                    else:
                        i += 1


                # Old, single-character replacees only
                # for char in raw_line:
                #     try:
                #         processed.extend(self.replacements[char])
                #     except KeyError:
                #         continue # probably \n but could also be special char
                
                if bool(self.shift_key) and self.shift_policy == "once":
                    i = len(processed) - 1
                    while i >= 2:
                        if (processed[i] == self.shift_key 
                            and processed[i-2] == self.shift_key):
                            processed.pop(i)
                        i -= 1

                if bool(self.repeat_key):
                    for i in range(1, len(processed)):
                        if processed[i] == processed[i-1]:
                            processed[i] = self.repeat_key
                        
                line = tuple(processed)
                self.key_counts.update(line)
                self.bigram_counts.update(itertools.pairwise(line))
                self.skip1_counts.update(zip(line, line[2:]))
                self.trigram_counts.update(
                    line[i:i+3] for i in range(len(line)-2))
                
                if not self.skipgram_weights:
                    continue
                    
                for i, l1 in enumerate(line):
                    for sep, weight in enumerate(self.skipgram_weights):
                        if i+sep < len(line):
                            self.skipgram_counts[(l1, line[i+sep])] += weight
        
    def set_precision(self, precision: int | None):
        # if self.trigram_precision_total and precision == self.precision:
        #     return
        if precision <= 0:
            self.precision = 0
            precision = len(self.top_trigrams)
        else:
            self.precision = precision
        self.top_trigrams = self.all_trigrams[:precision]
        self.trigram_precision_total = sum(self.trigram_counts[tg] 
            for tg in self.top_trigrams)
        self.trigram_completeness = (self.trigram_precision_total / 
            self.trigram_counts.total())
        self.filtered_trigram_counts = {t: self.trigram_counts[t] for t in self.top_trigrams}

    def _json_load(self, json_dict: dict):
        self.key_counts = Counter(json_dict["key_counts"])
        self.bigram_counts = eval(json_dict["bigram_counts"])
        self.skip1_counts = eval(json_dict["skip1_counts"])
        self.trigram_counts = eval(json_dict["trigram_counts"])
        self.skipgram_counts = eval(json_dict["skipgram_counts"])
    
    def jsonable_export(self):
        return {
            "filename": self.filename,
            "space_key": self.space_key,
            "shift_key": self.shift_key,
            "shift_policy": self.shift_policy,
            "special_replacements": self.special_replacements,
            "repeat_key": self.repeat_key,
            "key_counts": self.key_counts,
            "bigram_counts": repr(self.bigram_counts),
            "skip1_counts": repr(self.skip1_counts),
            "trigram_counts": repr(self.trigram_counts),
            "skipgram_weights": self.skipgram_weights,
            "skipgram_counts": repr(self.skipgram_counts)
        }

    def _translate(self, other: Type["Corpus"]):
        if self.shift_policy != other.shift_policy:
            raise TranslationError("Mismatched shifting policies")
        if bool(self.space_key) != bool(other.space_key):
            raise TranslationError(f"Cannot translate missing space key")
        if bool(self.shift_key) != bool(other.shift_key):
            raise TranslationError(f"Cannot translate missing shift key")
        if self.special_replacements != other.special_replacements:
            raise TranslationError("Cannot translate differing special_replacements")
        if bool(self.repeat_key) != bool(other.repeat_key):
            raise TranslationError("Cannot translate missing repeat key")
        if self.skipgram_weights != other.skipgram_weights:
            raise TranslationError("Cannot translate differing skipgram weights")

        self.replacements = create_replacements(
            self.space_key, self.shift_key, self.special_replacements
        )
        conversion: dict[str, str] = {}
        conversion[other.space_key] = self.space_key
        conversion[other.shift_key] = self.shift_key
        conversion[other.repeat_key] = self.repeat_key
        self.key_counts = Counter()
        for ko, count in other.key_counts.items():
            self.key_counts[conversion.get(ko, ko)] = count
        self.bigram_counts = Counter()
        for bo, count in other.bigram_counts.items():
            self.bigram_counts[
                tuple(conversion.get(ko, ko) for ko in bo)] = count
        self.trigram_counts = Counter()
        for to, count in other.trigram_counts.items():
            self.trigram_counts[
                tuple(conversion.get(ko, ko) for ko in to)] = count
        self.skipgram_counts = Counter()
        for so, count in other.skipgram_counts.items():
            self.skipgram_counts[
                tuple(conversion.get(ko, ko) for ko in so)] = count

# All corpuses, including translations
loaded = [] # type: list[Corpus]
# Exclude translations
disk_list = [] # type: list[Corpus]

def get_corpus(filename: str, 
               space_key: str = "space",
               shift_key: str = "shift",
               shift_policy: str = "once",
               special_replacements: dict[str, tuple[str,...]] = {},
               repeat_key: str = "",
               precision: int = 500,
               skipgram_weights: tuple[float] = None):
    
    any_loaded = False
    for c in loaded:
        if c.filename == filename:
            any_loaded = True
            break
    if not any_loaded:
        _load_corpus_list(filename, precision)
    
    # find exact match
    for corpus_ in loaded:
        if (
            corpus_.filename == filename and
            corpus_.space_key == space_key and
            corpus_.shift_key == shift_key and
            corpus_.shift_policy == shift_policy and
            corpus_.special_replacements == special_replacements and
            corpus_.repeat_key == repeat_key and
            corpus_.skipgram_weights == skipgram_weights
        ):
            corpus_.set_precision(precision)
            return corpus_
    
    # try translation
    for corpus_ in loaded:
        try:
            new_ = Corpus(filename, space_key, shift_key, shift_policy, 
                special_replacements, precision, repeat_key, None, corpus_,
                skipgram_weights)
        except TranslationError:
            continue # translation unsuccessful
        loaded.append(new_)
        return new_

    # create entire new one
    new_ = Corpus(filename, space_key, shift_key, shift_policy, 
        special_replacements, precision, repeat_key, 
        skipgram_weights=skipgram_weights)
    loaded.append(new_)
    disk_list.append(new_)
    _save_corpus_list(filename)
    return new_

def _load_corpus_list(filename: str, precision: int = 500):
    try:
        with open(f"corpus/{filename}.json") as file:
            json_list: list[dict] = json.load(file)
    except FileNotFoundError:
        return
    result = []
    for c in json_list:
        filename = c["filename"]
        space_key = c.get("space_key", "")
        shift_key = c.get("shift_key", "")
        shift_policy = c["shift_policy"]
        special_replacements = c.get("special_replacements", {})
        repeat_key = c.get("repeat_key", "")
        skipgram_weights = c.get("skipgram_weights", None)
        result.append(Corpus(
            filename, space_key, shift_key, shift_policy, 
            special_replacements, precision, repeat_key, json_dict=c,
            skipgram_weights=skipgram_weights
        ))
    loaded.extend(result)
    disk_list.extend(result)

def _save_corpus_list(filename: str):
    with open(f"corpus/{filename}.json", "w") as file:
        json.dump(
            [c.jsonable_export() for c in disk_list 
                if c.filename == filename],
            file
        )

if __name__ == "__main__":
    print("Corpus test")
    corp = Corpus("tr_quotes.txt")
    print(corp.key_counts)
    print(corp.trigram_counts.most_common(20))
    print(len(corp.trigram_counts))
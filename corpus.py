# Load and process a corpus into trigram frequencies, subject to certain settings
# Members:
    # shift_key: str
    # space_key: str
    # key_counts: dict[str, int]
    # bigram_counts: dict[Bigram, int]
    # trigram_counts: dict[Trigram, int]
    # trigrams_by_freq: list[Trigram] - possibly just use trigram_counts.most_common()
    # trigram_precision: int
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

default_lower = """`1234567890-=qwertyuiop[]\asdfghjkl;'zxcvbnm,./"""
default_upper = """~!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:"ZXCVBNM<>?"""

def create_replacements(space_key: str, shift_key: str, 
        special_replacements: dict[str, tuple[str,...]]):
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

class Corpus:

    def __init__(self, filename: str, 
                 space_key: str = "space", 
                 shift_key: str = "shift", 
                 shift_policy: str = "once",
                 special_replacements: dict[str, tuple[str,...]] = {},
                 precision: int = 500, 
                 json_dict: dict = None, other: Type["Corpus"] = None) -> None:
        """shift_policy can be "once" or "each". "once" means that when 
        consecutive capital letters occur, shift is only pressed once before 
        the first letter. "each" means shift is pressed before each letter.
        """
        self.filename = filename
        self.space_key = space_key
        self.shift_key = shift_key
        self.shift_policy = shift_policy
        self.special_replacements = special_replacements

        if json_dict is not None:
            self._json_load(json_dict)
        elif other is not None:
            self._translate(other)
        else:
            self._process()
        
        self.set_precision(precision)

    def _process(self):
        self.replacements = create_replacements(
            self.space_key, self.shift_key, self.special_replacements
        )

        self.key_counts = Counter()
        self.bigram_counts = Counter()
        self.trigram_counts = Counter()

        with open("corpus/" + self.filename, errors="ignore") as file:
            for raw_line in file:
                processed = []
                for char in raw_line:
                    try:
                        processed.extend(self.replacements[char])
                    except KeyError:
                        continue
                
                if self.shift_policy == "once":
                    i = len(processed) - 1
                    while i >= 2:
                        if (processed[i] == self.shift_key 
                            and processed[i-2] == self.shift_key):
                            processed.pop(i)
                        i -= 1
                        
                line = tuple(processed)
                self.key_counts.update(line)
                self.bigram_counts.update(itertools.pairwise(line))
                self.trigram_counts.update(
                    line[i:i+3] for i in range(len(line)-2))
        
    def set_precision(self, precision: int):
        self.precision = precision
        self.trigrams_by_freq = tuple(
            item[0] for item in 
                self.trigram_counts.most_common(self.precision))
        self.trigram_precision_total = sum(self.trigram_counts[tg] 
            for tg in self.trigrams_by_freq)
        self.trigram_completeness = (self.trigram_precision_total / 
            self.trigram_counts.total())

    def _json_load(self, json_dict: dict):
        self.key_counts = eval(json_dict["key_counts"])
        self.bigram_counts = eval(json_dict["bigram_counts"])
        self.trigram_counts = eval(json_dict["trigram_counts"])
    
    def json_export(self):
        obj = {
            "filename": self.filename,
            "space_key": self.space_key,
            "shift_key": self.shift_key,
            "shift_policy": self.shift_policy,
            "special_replacements": self.special_replacements,
            "key_counts": repr(self.key_counts),
            "bigram_counts": repr(self.bigram_counts),
            "trigram_counts": repr(self.trigram_counts)
        }
        return json.dumps(obj)

    def _translate(self, other: Type["Corpus"]):
        if self.shift_policy != other.shift_policy:
            raise ValueError("Mismatched shifting policies")
        if bool(self.space_key) != bool(other.space_key):
            raise ValueError(f"Cannot translate missing space key")
        if bool(self.shift_key) != bool(other.shift_key):
            raise ValueError(f"Cannot translate missing shift key")

        self.replacements = create_replacements(
            self.space_key, self.shift_key, self.special_replacements
        )
        conversion: dict[str, str] = {}
        for k, vs in self.replacements.items():
            vo = other.replacements[k]
            if vs != vo:
                if len(vs) != len(vo) or len(vo) > 1:
                    raise ValueError(f"Cannot translate {vo} to {vs}")
                else:
                    conversion[vo] = [vs]
        self.key_counts = Counter()
        for ko, count in other.key_counts:
            self.key_counts[conversion.get(ko, ko)] = count
        self.bigram_counts = Counter()
        for bo, count in other.bigram_counts:
            self.bigram_counts[
                tuple(conversion.get(ko, ko) for ko in bo)] = count
        self.trigram_counts = Counter()
        for to, count in other.trigram_counts:
            self.trigram_counts[
                tuple(conversion.get(ko, ko) for ko in to)] = count

loaded: list[Type["Corpus"]] = [] # All corpuses, including translations
disk_list: list[Type["Corpus"]] = [] # Should be saved to cache

def get_corpus(filename: str, 
               space_key: str = "space",
               shift_key: str = "shift",
               shift_policy: str = "once",
               special_replacements: dict[str, tuple[str,...]] = {},
               precision: int = 500):
    
    if not loaded:
        _load_corpus_list(precision)
        disk_list.extend(loaded)
    
    # find exact match
    for corpus_ in loaded:
        if (
            corpus_.filename == filename and
            corpus_.space_key == space_key and
            corpus_.shift_key == shift_key and
            corpus_.shift_policy == shift_policy and
            corpus_.special_replacements == special_replacements
        ):
            corpus_.set_precision(precision)
            return corpus_
    
    # try translation
    for corpus_ in loaded:
        if (corpus_.filename != filename or 
                bool(corpus_.space_key) != bool(space_key) or
                bool(corpus_.shift_key) != bool(shift_key) or
                corpus_.shift_policy != shift_policy):
            continue
        if special_replacements == corpus_.special_replacements:
            return corpus_
        replacements = create_replacements(
            space_key, shift_key, special_replacements)
        translatable = True
        for k, v in replacements.items():
            v2 = corpus_.replacements[k]
            if len(v) != len(v2) or len(v) > 1 and v != v2:
                translatable = False
                break
        if not translatable:
            continue
        new_ = Corpus(filename, space_key, shift_key, special_replacements, 
            precision, other=corpus_)
        loaded.append(new_)
        return new_

    # create entire new one
    new_ = Corpus(filename, space_key, shift_key, shift_policy, 
        special_replacements, precision)
    loaded.append(new_)
    disk_list.append(new_)
    _save_corpus_list(disk_list)
    return new_

def _load_corpus_list(precision: int = 500):
    try:
        with open("corpus/corpus_cache.json") as file:
            json_list = json.load(file)
    except OSError:
        return
    for c in json_list:
        filename = c["filename"]
        space_key = c["space_key"]
        shift_key = c["shift_key"]
        shift_policy = c["shift_policy"]
        special_replacements = c["special_replacements"]
        loaded.append(Corpus(
            filename, space_key, shift_key, shift_policy, 
            special_replacements, precision, c
        ))

def _save_corpus_list(l: list[Type["Corpus"]]):
    with open("corpus/corpus_cache.json", "w") as file:
        json.dump([c.json_export() for c in l], file)

if __name__ == "__main__":
    print("Corpus test")
    corp = Corpus("tr_quotes.txt")
    print(corp.key_counts)
    print(corp.trigram_counts.most_common(20))
    print(len(corp.trigram_counts))
# Contains analysis functionality accessed by commands.
# See commands.py for those commands, as well as the more REPL-oriented code.

from collections import Counter, defaultdict
import itertools
import math
import multiprocessing
import os
import random
import statistics
import typing
from typing import Callable, Collection, Iterable

from fingermap import Finger
import layout
import nstroke
import remap
from session import Session
from typingdata import TypingData

def data_for_tristroke_category(category: str, layout_: layout.Layout, 
        typingdata_: TypingData):
    """Returns (speed: float, num_samples: int, 
    with_fingers: dict[Finger, (speed: float, num_samples: int)],
    without_fingers: dict[Finger, (speed: float, num_samples: int)])
    using the *known* medians in the given tristroke category.

    Note that medians is the output of get_medians_for_layout()."""

    all_samples = []
    speeds_with_fingers = {finger: [] for finger in list(Finger)}
    speeds_without_fingers = {finger: [] for finger in list(Finger)}

    applicable = nstroke.applicable_function(category)

    for tristroke in typingdata_.exact_tristrokes_for_layout(layout_):
        cat = nstroke.tristroke_category(tristroke)
        if not applicable(cat):
            continue
        speed = typingdata_.tri_medians[tristroke][2]
        used_fingers = {finger for finger in tristroke.fingers}
        all_samples.append(speed)
        for finger in list(Finger):
            if finger in used_fingers:
                speeds_with_fingers[finger].append(speed)
            else:
                speeds_without_fingers[finger].append(speed)
    
    num_samples = len(all_samples)
    speed = statistics.fmean(all_samples) if num_samples else 0.0
    with_fingers = {}
    without_fingers = {}
    for speeds_l, output_l in zip(
            (speeds_with_fingers, speeds_without_fingers),
            (with_fingers, without_fingers)):
        for finger in list(Finger):
            n = len(speeds_l[finger])
            speed = statistics.fmean(speeds_l[finger]) if n else 0.0
            output_l[finger] = (speed, n)
    
    return (speed, num_samples, with_fingers, without_fingers)

def trigrams_in_list(
        trigrams: Iterable, typingdata_: TypingData, layout_: layout.Layout,
        corpus_settings: dict):
    """Returns dict[trigram_tuple, (freq, avg_ms, ms, is_exact)],
    except for the key \"\" which gives (freq, avg_ms, ms, exact_percent)
    for the entire given list."""
    raw = {"": [0, 0, 0]} # total_freq, total_time, known_freq for list
    speed_calc =  typingdata_.tristroke_speed_calculator(layout_)
    corpus_ = layout_.get_corpus(corpus_settings)
    for trigram in trigrams:
        if (tristroke := layout_.to_nstroke(trigram)) is None:
            continue
        try:
            count = corpus_.trigram_counts[trigram]
        except KeyError:
            continue
        speed, exact = speed_calc(tristroke)
        raw[""][0] += count
        raw[""][1] += speed*count
        if exact:
            raw[""][2] += count
        raw[trigram] = [count, speed*count, exact]
    raw[""][2] = raw[""][2]/raw[""][0] if raw[""][0] else 0
    result = dict()
    total_count = layout_.total_trigram_count(corpus_settings)
    for key in raw:
        freq = raw[key][0]/total_count if total_count else 0
        avg_ms = raw[key][1]/raw[key][0] if raw[key][0] else 0
        ms = raw[key][1]/total_count if total_count else 0
        result[key] = (freq, avg_ms, ms, raw[key][2])
    return result

def trigrams_with_specifications_raw(
        typingdata_: TypingData, corpus_settings: dict, 
        layout_: layout.Layout, category: str,
        with_fingers: set[Finger] = set(Finger), 
        without_fingers: set[Finger] = set(),
        with_keys: set[str] = set(),
        without_keys: set[str] = set()):
    """Returns total_layout_count and a 
    dict[trigram_tuple, (count, total_time, is_exact)].
    In the dict, the \"\" key gives the total 
    (count, total_time, exact_count) for the entire given category.
    """
    if not with_fingers:
        with_fingers.update(Finger)
    with_fingers.difference_update(without_fingers)
    if not with_keys:
        with_keys.update(layout_.positions)
    with_keys.difference_update(without_keys)
    applicable = nstroke.pplicable_function(category)
    result = {"": [0, 0, 0]} # total_count, total_time, known_count for category
    total_count = 0 # for all trigrams
    speed_calc =  typingdata_.tristroke_speed_calculator(layout_)
    for trigram, count in layout_.get_corpus(
            corpus_settings).trigram_counts.items():
        if (tristroke := layout_.to_nstroke(trigram)) is None:
            continue
        total_count += count
        if (with_keys.isdisjoint(trigram) 
                or not without_keys.isdisjoint(trigram)):
            continue
        if (with_fingers.isdisjoint(tristroke.fingers)
                or not without_fingers.isdisjoint(tristroke.fingers)):
            continue
        cat = nstroke.tristroke_category(tristroke)
        if not applicable(cat):
            continue
        speed, exact = speed_calc(tristroke)
        result[""][0] += count
        result[""][1] += speed*count
        if exact:
            result[""][2] += count
        result[tuple(trigram)] = [count, speed*count, exact]
    return total_count, result

def trigrams_with_specifications(
        typingdata_: TypingData, corpus_settings: dict, 
        layout_: layout.Layout, category: str, 
        with_fingers: set[Finger] = set(Finger), 
        without_fingers: set[Finger] = set(),
        with_keys: set[str] = set(),
        without_keys: set[str] = set()):
    """Returns dict[trigram_tuple, (freq, avg_ms, ms, is_exact)],
    except for the key \"\" which gives (freq, avg_ms, ms, exact_percent)
    for the entire given category."""
    layout_count, raw = trigrams_with_specifications_raw(
            typingdata_, corpus_settings, layout_, category,
            with_fingers, without_fingers, with_keys, without_keys)
    raw[""][2] = raw[""][2]/raw[""][0] if raw[""][0] else 0
    result = dict()
    for key in raw:
        freq = raw[key][0]/layout_count if layout_count else 0
        avg_ms = raw[key][1]/raw[key][0] if raw[key][0] else 0
        ms = raw[key][1]/layout_count if layout_count else 0
        result[key] = (freq, avg_ms, ms, raw[key][2])
    return result

def tristroke_breakdowns(medians: dict):
    """Returns a result such that result[category][bistroke] gives
    (speed, num_samples) for bistrokes obtained by breaking down tristrokes
    in that category. 

    This data is useful to estimate the speed of an unknown tristroke by 
    piecing together its component bistrokes, since those may be known.
    """
    samples = {cat: dict() for cat in nstroke.all_tristroke_categories}
    for ts in medians: # ts is tristroke
        cat = nstroke.tristroke_category(ts)
        bistrokes = (
            nstroke.Nstroke(ts.note, ts.fingers[:2], ts.coords[:2]),
            nstroke.Nstroke(ts.note, ts.fingers[1:], ts.coords[1:])
        )
        for i, b in enumerate(bistrokes):
            speed = medians[ts][i]
            try:
                samples[cat][b].append(speed)
            except KeyError:
                samples[cat][b] = [speed]
    result = {cat: dict() for cat in samples}
    for cat in samples:
        for bs in samples[cat]: # bs is bistroke
            mean = statistics.fmean(samples[cat][bs])
            count = len(samples[cat][bs])
            result[cat][bs] = (mean, count)
    return result

def layout_brief_analysis(layout_: layout.Layout, corpus_settings: dict, 
                          use_thumbs: bool = False):
    """
    Returns dict[stat_name, percentage]

    BAD BIGRAMS
    sfb (same finger)
    sfs
    vsb (vertical stretch)
    vss
    lsb (lateral stretch)
    lss
    asb (any stretch)
    ass

    GOOD BIGRAMS
    2roll-in
    2roll-out
    2roll-total
    in-out-ratio
    2alt

    ahs
    shs-best (shs-total - sfs - fss)
    shs-total

    TRIGRAMS
    redir-best
    redir-stretch
    redir-weak
    redir-sfs
    redir-total

    oneh-best
    oneh-stretch
    oneh-total

    alt-best (calculated from shs-best, redir-best, onehand-best)
    alt-sfs (calculated from sfs, sft, redirects-sfs)

    tutu-approx (2*2roll-total)

    sft
    """

    # any 2roll-total bigram can be part of 
    #   redir-total
    #   oneh-total
    #   3sfb-samehand (approximate as 3sfb/2 = 2sfb?)
    #   tutu

    # normally with a lone fsb, your trigram-incl-fsb category (call it 3fsb)
    # increases by 2. (2 3fsb per 1 2fsb). But when fsb chain into a fst, 
    # your 3fsb increases by 3 (fst in the middle), so 3 3fsb per 2 2fsb.
    # so the ratio goes off. but you can fix it by adding an extra fst,
    # so 2*fsb = 3fsb + fst. however in most cases fst is negligible
    #
    # Additionally, when you have a longer chain like fsq, it goes to 
    # 4 3fsb per 3 2fsb. so when you add back the 2 3fsb, it should also 
    # restore things to the right numbers.
    #
    # And if 2 2fsb right next to each other NOT overlapping, you
    # get 4 3fsb per 2 2fsb which is correct. so thats good
    #
    # But if you have a 2fsb at the start or end of a line, then
    # you only get 1 3fsb for that 2fsb, and there's no good way
    # to correct that. So that has to be accepted as inaccuracy. 
    # Overall 3fsb should therefore turn out to be lower than the fst
    # correction formula predicts.
    #
    # checking this with trialyzer sfb counts: 
    # trigram(sfb+sfr) = 4.28%, bigram(sfb+sfr) = 2.21%,
    # sft = 0.05%. 
    # Formula predicts 
    #   2*sfb = 3sfb + sft
    #   4.42% > 4.33%
    #   3sfb is indeed lower than the formula predicts.
    # Checking again with scissors:
    # trigram with scissor bigram = 1.85%, bigram scissors = 0.96%,
    # scissor_twice = 0.03%
    # Formula predicts 
    #   2*sbigram = 3scissor + scissor_twice
    #   1.92% > 1.85 + 0.03%
    #   3scissor is indeed lower than the formula predicts.
    # Could correct further by using the average length of a line in the corpus
    # but ehhhhhh
    #
    # ohhhh great what about skipgrams. they dont have the same problem
    # because there is no simple bigram thing we're trying to extrapolate from

    # the trigram-incl-fsb category (i think =2*fsb) is composed of
    #   redir-scissor (includes redir-sfs-scissor)
    #   oneh-scissor
    #   double-scissor versions of the above
    #   tutu-scissor -> this is 3fsb - redir-scissor - oneh-scissor.
    #                -> trigram-incl-fsb is 2*fsb + *-double-scissor

    # ahs trigrams break down into
    #   3sfb-handswitch (approximate as 3sfb/2 = 2sfb?)
    #   tutu-scissor
    #   tutu-best


    corpus_ = layout_.get_corpus(corpus_settings)
    pass # TODO

def layout_stats_analysis(layout_: layout.Layout, corpus_settings: dict, 
                          use_thumbs: bool = False):
    """
    Returns a tuple containing, in this order:
    * three Counters: one each for bigrams, skipgrams, and trigrams. Each is
      of the form dict[stat_name, percentage]
    * two dicts: one each for bigrams and skipgrams, listing the top three 
      bigrams in each category. Each is of the form dict[str, list[(str, str)]]

    BIGRAMS (skipgrams are the same, with same names. No parens)
    * sfb (same finger)
    * asb (any stretch)
    * vsb (vertical stretch)
    * lsb (lateral stretch)
    * ahb (alternate hand)
    * shb (same hand, other finger)
    * inratio

    TRIGRAMS
    * sft
    * inratio-trigram

    * redir-best
    * redir-stretch
    * redir-sfs
    * redir-weak
    * redir-total

    * alt-best
    * alt-stretch
    * alt-sfs
    * alt-total

    * oneh-best
    * oneh-stretch
    * oneh-total
    * inratio-oneh

    * roll-best
    * roll-stretch
    * roll-total
    * inratio-roll

    """
    corpus_ = layout_.get_corpus(corpus_settings)
    bstats = Counter()
    sstats = Counter()
    tstats = Counter()

    btop = defaultdict(list)
    stop = defaultdict(list)

    for dest, src, top in (
        (bstats, corpus_.bigram_counts, btop),
        (sstats, corpus_.skip1_counts, stop)
    ):
        bcount = 0
        for bg, count in src.items():
            if (bs := layout_.to_nstroke(bg)) is None:
                continue
            if (not use_thumbs) and any(
                f in (Finger.RT, Finger.LT) for f in bs.fingers):
                continue
            tags = nstroke.akl_bistroke_tags(bs)
            if not tags:
                continue # unknown bigram
            bcount += count
            for tag in tags:
                dest[tag] += count
                if len(top[tag]) < 3:
                    top[tag].append(bg)
        for label in dest:
            dest[label] /= bcount
        dest["inratio"] = dest["shb-in"]/(dest["shb"] - dest["shb-in"])
        
    tcount = 0
    for tg in corpus_.top_trigrams:
        if (ts := layout_.to_nstroke(tg)) is None:
            continue
        if (not use_thumbs) and any(
            f in (Finger.RT, Finger.LT) for f in ts.fingers):
            continue
        tags = nstroke.akl_tristroke_tags(ts)
        if not tags:
            continue # unknown trigram
        count = corpus_.trigram_counts[tg]
        tcount += count
        for tag in tags:
            tstats[tag] += count
    for label in tstats:
        tstats[label] /= tcount
    roll_out = tstats["roll-total"]-tstats["roll-in"]
    oneh_out = tstats["oneh-total"]-tstats["oneh-in"]
    tstats["inratio-roll"] = tstats["roll-in"]/roll_out
    tstats["inratio-oneh"] = tstats["oneh-in"]/oneh_out
    tstats["inratio-trigram"] = (tstats["oneh-in"] + 
        tstats["roll-in"])/(roll_out + oneh_out)

    return (bstats, sstats, tstats, btop, stop)

def layout_bistroke_analysis(layout_: layout.Layout, typingdata_: TypingData, 
        corpus_settings: dict):
    """Returns dict[category, (freq_prop, known_prop, speed, contribution)]
    
    bicatdata is the output of bistroke_category_data(). That is,
    dict[category: string, (speed: float, num_samples: int)]"""

    bigram_counts = layout_.get_corpus(corpus_settings).bigram_counts
    # {category: [total_time, exact_count, total_count]}
    by_category = {
        category: [0.0,0,0] for category in nstroke.all_bistroke_categories}
    bi_medians = typingdata_.amalgamated_bistroke_medians(layout_)
    bicatdata = typingdata_.bistroke_category_data(layout_)
    for bigram in bigram_counts:
        if (bistroke := layout_.to_nstroke(bigram)) is None:
            continue
        cat = nstroke.bistroke_category(bistroke)
        count = bigram_counts[bigram]
        if bistroke in bi_medians:
            speed = bi_medians[bistroke]
            by_category[cat][1] += count
        else:
            speed = bicatdata[cat][0]
        by_category[cat][0] += speed * count
        by_category[cat][2] += count
    
    # fill in sum categories
    for cat in nstroke.all_bistroke_categories:
        if not by_category[cat][2]:
            applicable = nstroke.applicable_function(cat)
            for othercat in nstroke.all_bistroke_categories:
                if by_category[othercat][2] and applicable(othercat):
                    for i in range(3):
                        by_category[cat][i] += by_category[othercat][i]

    total_count = by_category[""][2]
    if not total_count:
        total_count = 1
    stats = {}
    for cat in nstroke.all_bistroke_categories:
        cat_count = by_category[cat][2]
        if not cat_count:
            cat_count = 1
        freq_prop = by_category[cat][2] / total_count
        known_prop = by_category[cat][1] / cat_count
        cat_speed = by_category[cat][0] / cat_count
        contribution = by_category[cat][0] / total_count
        stats[cat] = (freq_prop, known_prop, cat_speed, contribution)
    
    return stats

def layout_tristroke_analysis(layout_: layout.Layout, typingdata_: TypingData,
    corpus_settings: dict):
    """Returns dict[category, (freq_prop, known_prop, speed, contribution)]
    
    tricatdata is the output of tristroke_category_data(). That is,
    dict[category: string, (speed: float, num_samples: int)]
    
    medians is the output of get_medians_for_layout(). That is, 
    dict[Tristroke, (float, float, float)]"""
    # {category: [total_time, exact_count, total_count]}
    by_category = {
        category: [0,0,0] for category in nstroke.all_tristroke_categories}
    speed_func = typingdata_.tristroke_speed_calculator(layout_)
    corpus_ = layout_.get_corpus(corpus_settings)
    for trigram in corpus_.top_trigrams:
        if (ts := layout_.to_nstroke(trigram)) is None:
            continue
        cat = nstroke.tristroke_category(ts)
        count = corpus_.trigram_counts[trigram]
        speed, is_exact = speed_func(ts)
        if is_exact:
            by_category[cat][1] += count
        by_category[cat][0] += speed * count
        by_category[cat][2] += count
    
    # fill in sum categories
    for cat in nstroke.all_tristroke_categories:
        if not by_category[cat][2]:
            applicable = nstroke.applicable_function(cat)
            for othercat in nstroke.all_tristroke_categories:
                if by_category[othercat][2] and applicable(othercat):
                    for i in range(3):
                        by_category[cat][i] += by_category[othercat][i]

    total_count = by_category[""][2]
    if not total_count:
        total_count = 1
    stats = {}
    for cat in nstroke.all_tristroke_categories:
        cat_count = by_category[cat][2]
        if not cat_count:
            cat_count = 1
        freq_prop = by_category[cat][2] / total_count
        known_prop = by_category[cat][1] / cat_count
        cat_speed = by_category[cat][0] / cat_count
        contribution = by_category[cat][0] / total_count
        stats[cat] = (freq_prop, known_prop, cat_speed, contribution)
    
    return stats

def layout_speed(
        layout_: layout.Layout, typingdata_: TypingData,
        corpus_settings: dict):
    """Like tristroke_analysis but instead of breaking down by category, only
    calculates stats for the "total" category.
    
    Returns (speed, known_prop)"""

    total_count, known_count, total_time = layout_speed_raw(
        layout_, typingdata_, corpus_settings)

    return (total_time/total_count, known_count/total_count)

def layout_speed_raw(
        layout_: layout.Layout, typingdata_: TypingData, corpus_settings: dict):
    """Returns (total_count, known_count, total_time)"""
    total_count = 0
    known_count = 0
    total_time = 0
    speed_func = typingdata_.tristroke_speed_calculator(layout_)
    corpus_ = layout_.get_corpus(corpus_settings)
    for trigram in corpus_.top_trigrams:
        if (ts := layout_.to_nstroke(trigram)) is None:
            continue
        count = corpus_.trigram_counts[trigram]
        speed, is_exact = speed_func(ts)
        if is_exact:
            known_count += count
        total_time += speed * count
        total_count += count
    return (total_count, known_count, total_time)

def finger_analysis(layout_: layout.Layout, typingdata_: TypingData,
        corpus_settings: dict):
    """Returns dict[finger, (freq, exact, avg_ms, ms)]
    
    finger has possible values including anything in Finger.names, 
    finger_names.values(), and hand_names.values()"""
    # {category: [cat_tcount, known_tcount, cat_ttime, lcount]}
    corpus_ = layout_.get_corpus(corpus_settings)
    letter_counts = corpus_.key_counts
    total_lcount = 0
    raw_stats = {finger.name: [0,0,0,0] for finger in Finger}
    raw_stats.update({
        nstroke.hand_names[hand]: [0,0,0,0] for hand in nstroke.hand_names})
    raw_stats.update(
        {nstroke.finger_names[fingcat]: [0,0,0,0] 
            for fingcat in nstroke.finger_names})
    speed_func = typingdata_.tristroke_speed_calculator(layout_)
    for key in layout_.keys.values():
        total_lcount += letter_counts[key]
        if total_lcount == 0:
            continue
        finger = layout_.fingers[key].name
        raw_stats[finger][3] += letter_counts[key]
        if finger == Finger.UNKNOWN.name:
            continue
        raw_stats[nstroke.hand_names[finger[0]]][3] += letter_counts[key]
        raw_stats[nstroke.finger_names[finger[1]]][3] += letter_counts[key]
    total_tcount = 0
    for trigram in corpus_.top_trigrams:
        if (tristroke := layout_.to_nstroke(trigram)) is None:
            continue
        tcount = corpus_.trigram_counts[trigram]
        total_tcount += tcount
        cats = set()
        for finger in tristroke.fingers:
            cats.add(finger.name)
            if finger != Finger.UNKNOWN:
                cats.add(nstroke.hand_names[finger.name[0]])
                cats.add(nstroke.finger_names[finger.name[1]])
        speed, is_exact = speed_func(tristroke)
        for cat in cats:
            if is_exact:
                raw_stats[cat][1] += tcount
            raw_stats[cat][2] += speed * tcount
            raw_stats[cat][0] += tcount
    processed = {}
    for cat in raw_stats:
        processed[cat] = (
            raw_stats[cat][3]/total_lcount if total_lcount else 0,
            raw_stats[cat][0]/total_tcount if total_tcount else 0, 
            raw_stats[cat][1]/raw_stats[cat][0] if raw_stats[cat][0] else 0,
            raw_stats[cat][2]/raw_stats[cat][0] if raw_stats[cat][0] else 0,
            raw_stats[cat][2]/total_tcount if total_tcount else 0, 
        )
    return processed

def key_analysis(layout_: layout.Layout, typingdata_: TypingData,
        corpus_settings: dict):
    """Like layout_tristroke_analysis but divided up by key.
    Each key only has data for trigrams that contain that key.
    
    Returns a result such that result[key][category] gives 
    (freq_prop, known_prop, speed, contribution)"""
    # {category: [total_time, exact_freq, total_freq]}
    raw = {key: {category: [0,0,0] for category in nstroke.all_tristroke_categories}
        for key in layout_.keys.values()}

    total_count = 0

    speed_func = typingdata_.tristroke_speed_calculator(layout_)
    corpus_ = layout_.get_corpus(corpus_settings)
    
    for trigram in corpus_.top_trigrams:
        if (ts := layout_.to_nstroke(trigram)) is None:
            continue
        cat = nstroke.tristroke_category(ts)
        count = corpus_.trigram_counts[trigram]
        speed, is_exact = speed_func(ts)
        for key in set(trigram):
            if is_exact:
                raw[key][cat][1] += count
            raw[key][cat][0] += speed * count
            raw[key][cat][2] += count
        total_count += count
    if not total_count:
            total_count = 1
    stats = {key: dict() for key in raw}
    for key in raw:
        # fill in sum categories
        for cat in nstroke.all_tristroke_categories:
            if not raw[key][cat][2]:
                applicable = nstroke.applicable_function(cat)
                for othercat in nstroke.all_tristroke_categories:
                    if raw[key][othercat][2] and applicable(othercat):
                        for i in range(3):
                            raw[key][cat][i] += raw[key][othercat][i]
        # process stats
        for cat in nstroke.all_tristroke_categories:
            cat_count = raw[key][cat][2]
            if not cat_count:
                cat_count = 1
            freq_prop = raw[key][cat][2] / total_count
            known_prop = raw[key][cat][1] / cat_count
            cat_speed = raw[key][cat][0] / cat_count
            contribution = raw[key][cat][0] / total_count
            stats[key][cat] = (freq_prop, known_prop, cat_speed, contribution)
    
    return stats

def steepest_ascent(layout_: layout.Layout, s: Session,
        pins: Iterable[str] = tuple(), suffix: str = "-ascended"):
    """Yields (newlayout, score, swap_made) after each step.
    """
    lay = layout.Layout(layout_.name, False, repr(layout_))
    if not lay.name.endswith(suffix):
        lay.name += suffix
    lay.name = find_free_filename(lay.name, prefix="layouts/")
    
    swappable = set(lay.keys.values())
    for key in pins:
        swappable.discard(key)

    total_count, known_count, total_time = layout_speed_raw(
        lay, s.typingdata_, s.corpus_settings
    )

    speed_func = s.typingdata_.tristroke_speed_calculator(layout_)
    speed_dict = {ts: speed_func(ts) for ts in lay.all_nstrokes()}

    lfreqs = layout_.get_corpus(s.corpus_settings).key_counts.copy()
    total_lcount = sum(lfreqs[key] for key in layout_.positions
        if key in lfreqs)
    for key in lfreqs:
        lfreqs[key] /= total_lcount

    unused_keys = set(key for key in lay.positions 
        if key not in lfreqs or not bool(lfreqs[key]))
        
    scores = [total_time/total_count]
    rows = tuple({pos.row for pos in lay.keys})
    cols = tuple({pos.col for pos in lay.keys})
    swaps = tuple(remap.swap(*pair) 
        for pair in itertools.combinations(swappable, 2))
    trigram_counts = lay.get_corpus(s.corpus_settings).filtered_trigram_counts
    with multiprocessing.Pool(4) as pool:
        while True:            
            row_swaps = (remap.row_swap(lay, r1, r2, pins) 
                for r1, r2 in itertools.combinations(rows, 2))
            col_swaps = (remap.col_swap(lay, c1, c2, pins) 
                for c1, c2 in itertools.combinations(cols, 2))

            args = (
                (remap, total_count, known_count, total_time, lay,
                    trigram_counts, speed_dict, unused_keys)
                for remap in itertools.chain(swaps, row_swaps, col_swaps)
                if s.constraintmap_.is_remap_legal(lay, lfreqs, remap))
            datas = pool.starmap(remapped_score, args, 200)
            try:
                best = min(datas, key=lambda d: d[2]/d[0])
            except ValueError:
                return # no swaps exist
            best_remap = best[3]
            best_score = best[2]/best[0]

            if best_score < scores[-1]:
                total_count, known_count, total_time = best[:3]
                scores.append(best_score)
                lay.remap(best_remap)
                
                yield lay, scores[-1], best_remap
            else:
                return # no swaps are good

def remapped_score(
        remap_: remap.Remap, total_count, known_count, total_time,
        lay: layout.Layout, trigram_counts: dict, 
        speed_func: typing.Union[Callable, dict], 
        exclude_keys: Collection[str] = ()):
    """
    For extra performance, filter trigram_counts by corpus precision.

    Returns:
    (total_count, known_count, total_time, remap)"""
    
    # for ngram in lay.ngrams_with_any_of(remap_, exclude_keys=exclude_keys):
    for ngram in trigram_counts: # probably faster
        # try:
        #     tcount = trigram_counts[ngram]
        # except KeyError: # contains key not in corpus
        #     continue
        affected_by_remap = False
        for key in ngram:
            if key in remap_:
                affected_by_remap = True
                break
        if not affected_by_remap:
            continue
        
        if (ts := lay.to_nstroke(ngram)) is None:
            continue
        tcount = trigram_counts[ngram]

        # remove effect of original tristroke
        try:
            speed, is_known = speed_func(ts)
        except TypeError:
            speed, is_known = speed_func[ts]
        if is_known:
            known_count -= tcount
        total_time -= speed * tcount
        total_count -= tcount
        
        # add effect of swapped tristroke
        ts = lay.to_nstroke(remap_.translate(ngram))
        try:
            speed, is_known = speed_func(ts)
        except TypeError:
            speed, is_known = speed_func[ts]
        if is_known:
            known_count += tcount
        total_time += speed * tcount
        total_count += tcount
    
    return (total_count, known_count, total_time, remap_)

def per_ngram_deltas(
        remap_: remap.Remap, 
        lay: layout.Layout, trigram_counts: dict, 
        speed_func: typing.Union[Callable, dict], 
        exclude_keys: Collection[str] = ()):
    """Calculates the stat deltas by ngram for the given remap. 
    Returns {ngram: delta_total_count, delta_known_count, delta_total_time}
    """

    result = {}

    for ngram in lay.ngrams_with_any_of(remap_, exclude_keys=exclude_keys):
        # deltas for the ngram
        known_count = 0
        total_time = 0
        total_count = 0

        try:
            tcount = trigram_counts[ngram]
        except KeyError: # contains key not in corpus
            continue
        
        # remove effect of original tristroke
        ts = lay.to_nstroke(ngram)
        try:
            speed, is_known = speed_func(ts)
        except TypeError:
            speed, is_known = speed_func[ts]
        if is_known:
            known_count -= tcount
        total_time -= speed * tcount
        total_count -= tcount
        
        # add effect of swapped tristroke
        ts = lay.to_nstroke(remap_.translate(ngram))
        try:
            speed, is_known = speed_func(ts)
        except TypeError:
            speed, is_known = speed_func[ts]
        if is_known:
            known_count += tcount
        total_time += speed * tcount
        total_count += tcount

        result[ngram] = (total_count, known_count, total_time)
    
    return result

def anneal(layout_: layout.Layout, s: Session,
        pins: Iterable[str] = tuple(), suffix: str = "-annealed",
        iterations: int = 10000):
    """Yields (layout, i, temperature, delta, score, remap) 
    when a remap is successful."""
    lay = layout.Layout(layout_.name, False, repr(layout_))
    if not lay.name.endswith(suffix):
        lay.name += suffix

    total_count, known_count, total_time = layout_speed_raw(
        lay, s.typingdata_, s.corpus_settings
    )

    speed_func = s.typingdata_.tristroke_speed_calculator(layout_)

    corpus_ = lay.get_corpus(s.corpus_settings)
    lfreqs = corpus_.key_counts.copy()
    total_lcount = sum(lfreqs[key] for key in layout_.positions
        if key in lfreqs)
    for key in lfreqs:
        lfreqs[key] /= total_lcount

    unused_keys = set(key for key in lay.positions 
        if key not in lfreqs or not bool(lfreqs[key]))
    
    scores = [total_time/total_count]
    T0 = 10
    Tf = 1e-3
    k = math.log(T0/Tf)

    rows = tuple({pos.row for pos in lay.keys})
    cols = tuple({pos.col for pos in lay.keys})
    remap_ = remap.Remap() # initialize in case needed for is_remap_legal() below

    random.seed()
    for i in range(iterations):
        temperature = T0*math.exp(-k*i/iterations)
        try_rowswap = i % 100 == 0
        if try_rowswap:
            remap_ = remap.row_swap(lay, *random.sample(rows, 2), pins)
        try_colswap = ((not try_rowswap) and i % 10 == 0
            or try_rowswap and not s.constraintmap_.is_remap_legal(
                lay, lfreqs, remap_))
        if try_colswap:
            remap_ = remap.col_swap(lay, *random.sample(cols, 2), pins)
        if (
                not (try_colswap or try_rowswap) or 
                (try_colswap or try_rowswap) and not 
                    s.constraintmap_.is_remap_legal(lay, lfreqs, remap_)):
            remap_ = s.constraintmap_.random_legal_swap(lay, lfreqs, pins)
        data = remapped_score(remap_, total_count, known_count, total_time,
            lay, corpus_.filtered_trigram_counts, speed_func, unused_keys)
        score = data[2]/data[0]
        delta = score - scores[-1]

        if score > scores[-1]:
            p = math.exp(-delta/temperature)
            if random.random() > p:
                continue

        total_count, known_count, total_time = data[:3]
        scores.append(score)
        lay.remap(remap_)
        
        yield lay, i, temperature, delta, scores[-1], remap_
    return

def find_free_filename(before_number: str, after_number: str = "", 
                       prefix = ""):
    """Returns the filename {before_number}{after_number} if not already taken,
    or else returns the filename {before_number}-{i}{after_number} with the 
    smallest i that results in a filename not already taken.
    
    prefix is used to specify a prefix that is applied to the filename
    but is not part of the returned value, used for directory things."""
    incl_number = before_number
    i = 1
    while os.path.exists(prefix + incl_number + after_number):
        incl_number = f"{before_number}-{i}"
        i += 1
    return incl_number + after_number
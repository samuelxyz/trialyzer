# `Command`s bundle names/aliases, help-strings, and functionality.
# Also defines all the individual commands in trialyzer.
# Also contains backend functions which are useful for the commands.

import csv
import curses
import enum
import math
import operator
import os
import statistics
from typing import Callable, Iterable
import time

import analysis
import constraintmap
import corpus
from fingermap import Finger
import gui_util
import layout
import nstroke
import remap
from session import Session
from typingdata import TypingData
import typingtest

class CommandType(enum.Enum):
    GENERAL = enum.auto()
    DATA = enum.auto()
    ANALYSIS = enum.auto()
    EDITING = enum.auto()

class Command:    
    
    def __init__(self, type: CommandType, help: tuple[str], names: tuple[str], 
                 fn: Callable[[list[str], Session], str | None]):
        """
        `names` is a list of aliases that the user can use to activate the 
        command. The first of these will be use to alphabetize commands.
        
        The first string of `help` will be used as a brief summary when the 
        `help` command is used with no args. The rest will be joined with 
        newlines.
        
        `fn` is the actual function to be run, with parameters being 
        `args: str` and `session`. It is usually void, but may return `"quit"`
        to trigger application exit.
        """
        self.names = names
        self.type = type
        self.help = help
        self.fn = fn

commands = list()
by_name = dict()

def register_command(cmd: Command):
    commands.append(cmd)
    for name in cmd.names:
        by_name[name] = cmd

def run_command(name: str, args: list[str], s: Session):
    cmd = by_name.get(name, None)
    if cmd is None:
        s.say("Unrecognized command", gui_util.red)
    else:
        return cmd.fn(args, s)
    
# Actual commands

def cmd_type(args: list[str], s: Session):
    if not args: # autosuggest trigram
        # Choose the most frequent trigram from the least completed 
        # category of the analysis target layout
        exact_tristrokes = s.typingdata_.exact_tristrokes_for_layout(
            s.analysis_target)
        catdata = s.typingdata_.tristroke_category_data(s.analysis_target)
        s.analysis_target.preprocessors["counts"].join()
        counts = s.analysis_target.counts
        completion = {}
        for cat in catdata:
            if cat.startswith(".") or cat.endswith(".") or cat == "":
                continue
            n = catdata[cat][1]
            completion[cat] = n/counts[cat] if n > 0 else 0

        ruled_out = {s.analysis_target.to_ngram(tristroke)
            for tristroke in exact_tristrokes} # already have data
        user_tg = None

        def find_from_best_cat():
            if not completion:
                return None
            best_cat = min(completion, key = lambda cat: completion[cat])
            # is sorted by descending frequency
            for tg in s.target_corpus.trigram_counts:
                if tg in ruled_out:
                    continue
                if (tristroke := s.analysis_target.to_nstroke(tg)) is None:
                    continue
                if nstroke.tristroke_category(tristroke) == best_cat:
                    ruled_out.add(tg)
                    if s.user_layout.to_ngram(tristroke): # keys exist
                        return tristroke
            # if we get to this point, 
            # there was no compatible trigram in the category
            # Check next best category
            del completion[best_cat]
            return find_from_best_cat()
        
        tristroke = find_from_best_cat()
        user_tg = s.user_layout.to_ngram(tristroke)
        targ_tg = s.analysis_target.to_ngram(tristroke)
        if not tristroke:
            s.say("Unable to autosuggest - all compatible trigrams"
                " between the user layout and analysis target"
                " already have data", gui_util.red)
            return
        else:
            estimate, _ = s.typingdata_.tristroke_speed_calculator(
                s.analysis_target)(tristroke)
            # TODO: frequency?
            fingers = tuple(finger.name for finger in tristroke.fingers)
            freq = (s.target_corpus.trigram_counts[targ_tg]/
                s.target_corpus.trigram_counts.total())
            s.say(f"Autosuggesting trigram "
                f"{corpus.display_str(user_tg, s.corpus_settings)}\n"
                f"({s.analysis_target.name} "
                f"{corpus.display_str(targ_tg, s.corpus_settings)})\n" +
                "Be sure to use {} {} {}".format(*fingers) + 
                f"\nFrequency: {freq:.3%}",
                gui_util.blue)
    elif args[0] == "cat":
        args.pop(0)
        with_fingers = set()
        without_fingers = set()
        with_keys = set()
        without_keys = set()
        for i in reversed(range(len(args))):
            if args[i] == "with":
                for _ in range(len(args)-i-1):
                    item = args.pop()
                    try:
                        with_fingers.add(Finger[item])
                    except KeyError:
                        with_keys.add(item)
                        with_keys.add(item)
                        with_keys.add(
                            corpus.display_name(item, s.corpus_settings))
                        with_keys.add(
                            corpus.undisplay_name(item, s.corpus_settings))
                args.pop() # remove "with"
            elif args[i] == "without":
                for _ in range(len(args)-i-1):
                    item = args.pop()
                    try:
                        without_fingers.add(Finger[item])
                    except KeyError:
                        without_keys.add(item)
                        without_keys.add(
                            corpus.display_name(item, s.corpus_settings))
                        without_keys.add(
                            corpus.undisplay_name(item, s.corpus_settings))
                args.pop() # remove "without"
        if not with_fingers:
            with_fingers.update(Finger)
        with_fingers -= without_fingers
        if not with_keys:
            with_keys.update(s.analysis_target.positions)
        with_keys -= without_keys
        if not args:
            category = ""
        else:
            category = nstroke.parse_category(args[0])
        exact_tristrokes = s.typingdata_.exact_tristrokes_for_layout(
            s.analysis_target)
        targ_tg = None
        applicable = nstroke.applicable_function(category)
        for tg in s.target_corpus.trigram_counts:
            if with_keys and with_keys.isdisjoint(tg):
                continue
            if (ts := s.analysis_target.to_nstroke(tg)) is None:
                continue
            if not applicable(nstroke.tristroke_category(ts)):
                continue
            if ts in exact_tristrokes:
                continue
            if with_fingers.isdisjoint(ts.fingers):
                continue
            reject = False
            for finger in ts.fingers:
                if finger in without_fingers:
                    reject = True
                    break
            if reject:
                continue
            targ_tg = tg
            user_tg = s.user_layout.to_ngram(ts)
            tristroke = ts
            break
        if targ_tg is None:
            s.say("Unable to autosuggest - all trigrams"
                " matching these specs already have data", gui_util.red)
            return
        else:
            estimate, _ = s.typingdata_.tristroke_speed_calculator(
                s.analysis_target)(tristroke)
            fingers = tuple(finger.name for finger in tristroke.fingers)
            freq = (s.target_corpus.trigram_counts[targ_tg]/
                s.target_corpus.trigram_counts.total())
            s.say(f"Autosuggesting trigram "
                f"{nstroke.display_str(user_tg, s.corpus_settings)}\n"
                f"({s.analysis_target.name} "
                f"{nstroke.display_str(targ_tg, s.corpus_settings)})\n" +
                "Be sure to use {} {} {}".format(*fingers) + 
                f"\nFrequency: {freq:.3%}",
                gui_util.blue)
    else:
        if len(args) == 1:
            args = tuple(args)
        if len(tuple(args)) != 3:
            s.say("Trigram must be length 3", gui_util.red)
            return
        if (tristroke := s.user_layout.to_nstroke(tuple(args))) is None:                
            s.say("That trigram isn't in this layout", gui_util.red)
            return
        estimate, _ = s.typingdata_.tristroke_speed_calculator(
            s.user_layout)(tristroke)
        user_corp = s.user_layout.get_corpus(s.corpus_settings)
        try:
            freq = (
                user_corp.trigram_counts[s.user_layout.to_ngram(tristroke)]/
                user_corp.trigram_counts.total())
            s.say(f"\nFrequency: {freq:.3%}", gui_util.blue)
        except (KeyError, TypeError):
            freq = None
    csvdata = s.typingdata_.csv_data
    if tristroke in csvdata:
        s.say(
            f"Note: this tristroke already has "
            f"{len(csvdata[tristroke][0])} data points",
            gui_util.blue)
    s.say("Starting typing test >>>", gui_util.green)
    typingtest.test(s, tristroke, estimate)
    s.input_win.clear()
    s.typingdata_.save_csv()
    s.say("Typing data saved", gui_util.green)
    s.typingdata_.refresh()

register_command(Command(
    CommandType.DATA,
    (
        "t[ype] [trigram]: Run typing test\n"
        "t[ype] cat [category] [with <fingers/keys>] [without <fingers/keys>]:"
            " Run typing test with trigram of a certain type",
        "If no argument is given, a trigram is autosuggested based on the "
            "analysis target."
    ),
    ("type", "t"),
    cmd_type
))

def cmd_clear(args: list[str], s: Session):
    if len(args) == 3:
        trigram = tuple(args)
    elif len(args) == 1 and len(args[0]) == 3:
        trigram = tuple(args[0])
    else:
        s.say("Usage: c[lear] <trigram>", gui_util.red)
        return
    csvdata = s.typingdata_.csv_data
    if (tristroke := s.user_layout.to_nstroke(trigram)) is None:                
        if (tristroke := s.user_layout.to_nstroke(tuple(
                corpus.undisplay_name(key, s.corpus_settings) 
                for key in trigram))) is None:
            s.say("That trigram does not exist in the user layout",
                gui_util.red)
            return
    try:
        num_deleted = len(csvdata.pop(tristroke)[0])
    except KeyError:
        num_deleted = 0
    s.typingdata_.save_csv()
    s.typingdata_.refresh()
    s.say(f"Deleted {num_deleted} data points for "
        f"{corpus.display_str(trigram, s.corpus_settings)}")
    
register_command(Command(
    CommandType.DATA,
    ("c[lear] <trigram>: Erase data for trigram",),
    ("clear", "c"),
    cmd_clear
))

def cmd_target(args: list[str], s: Session):
    layout_name = " ".join(args)
    if layout_name: # set layout
        try:
            s.analysis_target = layout.get_layout(layout_name)
            s.say("Set " + layout_name + " as the analysis target.",
                    gui_util.green)
            s.corpus_settings["repeat_key"] = s.analysis_target.repeat_key
            s.target_corpus = s.analysis_target.get_corpus(s.corpus_settings)
            s.save_settings()
        except FileNotFoundError:
            s.say(f"/layouts/{layout_name} was not found.", 
                    gui_util.red)
    else:
        s.say("Usage: target <layout name>", gui_util.red)

register_command(Command(
    CommandType.GENERAL,
    (
        "target <layout name>: Set analysis target (for further commands)",
        "Not to be confused with use"
    ),
    ("target"),
    cmd_target
))

def cmd_layout(args: list[str], s: Session):
    layout_name = " ".join(args)
    if layout_name:
        try:
            s.output("\n"+ layout_name + "\n" + 
                     limited_repr(layout.get_layout(layout_name)))
        except FileNotFoundError:
            s.say(f"/layouts/{layout_name} was not found.",
                gui_util.red)
            s.say("Searching for similar layouts...",
                gui_util.blue)
            return cmd_layouts(args, s)
    else:
        s.output("\n" + s.analysis_target.name + "\n"
                + limited_repr(s.analysis_target))

register_command(Command(
    CommandType.GENERAL,
    (
        "l[ayout] [layout name]: View layout", 
        "If no argument given, uses the target layout.\n"
        "Searches for similar layouts if no match found."
    ),
    ("layout", "l"),
    cmd_layout
))

def cmd_layouts(args: list[str], s: Session):
    if not args:
        s.say("Missing search terms. Did you mean 'list'?", gui_util.red)
        return
    layout_names = scan_dir()
    if not layout_names:
        s.say("No layouts found in /layouts/", gui_util.red)
        return
    layouts: list[layout.Layout] = []
    for name in layout_names:
        for str_ in args:
            if str_ in name:
                layouts.append(layout.get_layout(name))
                break
    if not layouts:
        s.say(f"No layouts matched these terms")
        return
    for l in layouts:
        s.output(f"\n{l.name}\n{repr(l)}")

register_command(Command(
    CommandType.GENERAL,
    (
        "layouts <search terms>: View multiple layouts",
        "Uses the target layout if none specified"
    ),
    ("layouts",),
    cmd_layouts
))

def cmd_list(args: list[str], s: Session):
    try:
        page_num = int(args[0])
    except IndexError:
        page_num = 1
    except ValueError:
        s.say("Usage: list [page]", gui_util.red)
        return
    layout_file_list = scan_dir()
    if not layout_file_list:
        s.say("No layouts found in /layouts/", gui_util.red)
        return
    s.output(f"{len(layout_file_list)} layouts found")
    first_row = 3
    num_rows = s.right_pane.getmaxyx()[0] - first_row
    names = [str(layout.get_layout(filename)) 
        for filename in layout_file_list]
    col_width = len(max(names, key=len))
    padding = 3
    num_cols =  (1 + 
        (s.right_pane.getmaxyx()[1] - col_width) // (col_width + padding))
    num_pages = math.ceil(len(names) / (num_rows * num_cols))
    if page_num > num_pages:
        page_num = num_pages
    elif page_num <= 0:
        page_num = 1
    s.output(f"Page {page_num} of {num_pages}"
        + " - Use list [page] to view others" * (num_pages > 1)
        + "\n---", )
    first_index = (page_num - 1) * num_rows * num_cols
    last_index = min(len(names), first_index + num_rows * num_cols)
    s.right_pane.scroll(num_rows)
    for i in range(last_index - first_index):
        s.right_pane.addstr(
            first_row + i % num_rows, 
            (i // num_rows) * (col_width + padding),
            names[first_index + i])
    s.right_pane.refresh()

register_command(Command(
    CommandType.GENERAL,
    ("list|ls [page]: List all layouts",),
    ("list", "ls"),
    cmd_list
))

def cmd_use(args: list[str], s: Session):
    layout_name = " ".join(args)
    if not layout_name:
        s.say("Usage: u[se] <layout name>", gui_util.red)
        return
    try:
        s.user_layout = layout.get_layout(layout_name)
        s.say("Set " + layout_name + " as the user layout.",
                gui_util.green)
        s.save_settings()
    except FileNotFoundError:
        s.say(f"/layouts/{layout_name} was not found.", 
                gui_util.red)

register_command(Command(
    CommandType.DATA,
    (
        "u[se] <layout name>: Set user layout (for typing test, etc)",
        "Not to be confused with target"
    ),
    ("use", "u"),
    cmd_use
))

def cmd_alias(args: list[str], s: Session):
    remove = False
    if not args:
        s.say("Usage:\n" + "\n".join((
            "alias <key1> <key2> [key3, ...]: "
                "Set equivalent keys in typing test",
            "alias list: Show existing aliases",
            "alias remove <key1> <key2> [key3, ...]: Remove alias",
        )), gui_util.red)
        return
    elif args[0] == "list":
        if s.key_aliases:
            s.say("Existing aliases:", gui_util.blue)
            for keys in s.key_aliases:
                s.say(" <-> ".join(keys), gui_util.blue)
        else:
            s.say("No existing aliases", gui_util.blue)
        return
    elif args[0] == "remove":
        remove = True
        args.pop(0)
    
    if len(args) < 2:
        s.say("At least two keys must be specified", gui_util.red)
        return

    keys = frozenset(args)
    if remove:
        try:
            s.key_aliases.remove(keys)
            s.say("Removed alias", gui_util.green)
        except ValueError:
            s.say("That alias wasn't there", gui_util.red)
            for a in s.key_aliases:
                if keys < a:
                    s.say(f"Maybe you meant {' '.join(a)}?")
                    break
            return
    else:
        if keys not in s.key_aliases:
            s.key_aliases.add(keys)
            s.say("Added alias", gui_util.green)
        else:
            s.say("That alias already exists", gui_util.green)
            return

    s.save_settings()

register_command(Command(
    CommandType.DATA,
    (
        "alias <key1> <key2> [key3, ...]: Set equivalent keys in typing test\n"
            "alias list: Show existing aliases\n"
            "alias remove <key1> <key2> [key3, ...]: Remove alias",
        "This is intended for making the typing test more convenient. "
            "Keys added in the same command form a group. Keys in a group are "
            "considered equivalent to each other in the typing test. "
            "Groups are not transitive, eg. with groups (a, b) and (b, c), "
            "a will not work as an alias for c."
    ),
    ("alias",),
    cmd_alias
))

def cmd_analyze_diff_common(s: Session, baseline_layout: layout.Layout, 
        target_layout: layout.Layout, show_all: bool, hint: str):
    
    base_tri_stats = analysis.layout_tristroke_analysis(
        baseline_layout, s.typingdata_, s.corpus_settings)
    base_bi_stats = analysis.layout_bistroke_analysis(
        baseline_layout, s.typingdata_, s.corpus_settings)
    base_tri_ms = base_tri_stats[""][2]
    base_tri_wpm = 24000/base_tri_ms
    base_bi_ms = base_bi_stats[""][2]
    base_bi_wpm = 12000/base_bi_ms

    tar_tri_stats = analysis.layout_tristroke_analysis(
        target_layout, s.typingdata_, s.corpus_settings)
    tar_bi_stats = analysis.layout_bistroke_analysis(
        target_layout, s.typingdata_, s.corpus_settings)
    tar_tri_ms = tar_tri_stats[""][2]
    tar_tri_wpm = 24000/tar_tri_ms
    tar_bi_ms = tar_bi_stats[""][2]
    tar_bi_wpm = 12000/tar_bi_ms

    def diff(target, baseline):
        return {key: 
            tuple(map(operator.sub, target[key], baseline[key]))
            for key in target}

    tri_stats = diff(tar_tri_stats, base_tri_stats)
    bi_stats = diff(tar_bi_stats, base_bi_stats)
    tri_ms = tar_tri_ms - base_tri_ms
    tri_wpm = tar_tri_wpm - base_tri_wpm
    bi_ms = tar_bi_ms - base_bi_ms
    bi_wpm = tar_bi_wpm - base_bi_wpm

    s.output(f"\nLayout {target_layout} relative to {baseline_layout}")
    s.output(f"Overall {tri_ms:+.2f} ms per trigram ({tri_wpm:+.2f} wpm)")
    s.output(f"Overall {bi_ms:+.2f} ms per bigram ({bi_wpm:+.2f} wpm)")
    
    tri_header_line = (
        "\nTristroke categories         freq    exact   avg_ms      ms")
    bi_header_line = (
        "\nBistroke categories          freq    exact   avg_ms      ms")

    if show_all:
        tri_disp = tri_stats
        bi_disp = bi_stats
    else:
        tri_disp = {cat: vals for (cat, vals) in tri_stats.items()
            if (tar_tri_stats[cat][0] or base_tri_stats[cat][0]) and not (
                "scissor" in cat[2:] or "sfr" in cat or "sft" in cat)}
        bi_disp = {cat: vals for (cat, vals) in bi_stats.items()
            if (tar_bi_stats[cat][0] or base_bi_stats[cat][0]) and (
                "scissor" not in cat or cat.startswith("."))}

    print_analysis_stats(tri_disp, tri_header_line, True)
    if not show_all:
        s.output(f"Use command \"{hint}\" to see remaining categories")
    print_analysis_stats(bi_disp, bi_header_line, True)

def cmd_analyze(args: list[str], s: Session, show_all: bool = False):
    if args:
        layout_name = " ".join(args)
        try:
            target_layout = layout.get_layout(layout_name)
        except FileNotFoundError:
            s.say(f"/layouts/{layout_name} was not found.", 
                    gui_util.red)
            return
    else:
        target_layout = s.analysis_target
    s.say("Crunching the numbers >>>", gui_util.green)
    s.repl_win.refresh()
    
    tri_stats = analysis.layout_tristroke_analysis(
        target_layout, s.typingdata_, s.corpus_settings)
    bi_stats = analysis.layout_bistroke_analysis(
        target_layout, s.typingdata_, s.corpus_settings)
    
    tri_ms = tri_stats[""][2]
    tri_wpm = int(24000/tri_ms) if tri_ms else 0.0
    bi_ms = bi_stats[""][2]
    bi_wpm = int(12000/bi_ms) if bi_ms else 0.0

    s.output(f"\nLayout: {target_layout}")
    s.output(f"Overall {tri_ms:.1f} ms per trigram ({tri_wpm} wpm)")
    s.output(f"Overall {bi_ms:.1f} ms per bigram ({bi_wpm} wpm)")
    
    tri_header_line = (
        "\nTristroke categories         freq    exact   avg_ms      ms")
    bi_header_line = (
        "\nBistroke categories          freq    exact   avg_ms      ms")

    if show_all:
        tri_disp = tri_stats
        bi_disp = bi_stats
    else:
        tri_disp = {cat: vals for (cat, vals) in tri_stats.items()
            if vals[0] and not (
                "scissor" in cat[2:] or "sfr" in cat or "sft" in cat)}
        bi_disp = {cat: vals for (cat, vals) in bi_stats.items()
            if vals[0] and ("scissor" not in cat or cat.startswith("."))}

    print_analysis_stats(s, tri_disp, tri_header_line)
    if not show_all:
        s.output("Use command \"fulla[nalyze]\" "
            "to see remaining categories")
    print_analysis_stats(s, bi_disp, bi_header_line)

register_command(Command(
    CommandType.ANALYSIS,
    (
        "a[nalyze] [layout name]: Detailed layout analysis",
        "Uses target layout if no args given.\n"
            "This is the main special feature of trialyzer. Uses the selected "
            "typing speed data.\n"
            "Shows only a more interesting selection of "
            "tristroke categories, for brevity - use fullanalyze to see them "
            "all."
    ),
    ("analyze", "analyse", "a"),
    cmd_analyze
))

register_command(Command(
    CommandType.ANALYSIS,
    (
        "fulla[nalyze] [layout name]: Like analyze but shows all tristroke "
            "categories",
        "Use analyze to see a more concise version."
    ),
    ("fullanalyze", "fulla", "fullanalyse"),
    lambda args, s: cmd_analyze(args, s, True)
))

def cmd_analyze_diff(args: list[str], s: Session, show_all: bool = False):

    if not args:
        s.say("Usage: adiff [baseline_layout] <layout>", gui_util.red)
        return
    
    baseline_layout = None
    lay1, remain = extract_layout_front(args)
    if lay1:
        if remain:
            lay2, _ = extract_layout_front(remain, True)
            if lay2:
                baseline_layout, target_layout = lay1, lay2
            else:
                s.say(f"/layouts/{' '.join(remain)} was not found.",
                    gui_util.red)
                return
        else:
            baseline_layout, target_layout = s.analysis_target, lay1
    else:
        s.say(f"/layouts/{' '.join(args)} was not found.",
            gui_util.red)
        return
    
    s.say("Crunching the numbers >>>", gui_util.green)
    s.repl_win.refresh()
    
    cmd_analyze_diff_common(s, baseline_layout, target_layout, 
                        show_all, "fulladiff")
    
register_command(Command(
    CommandType.ANALYSIS,
    (
        "a[nalyze]diff [baseline_layout] <layout>: "
            "Like analyze but compares two layouts",
        "Shows the incremental stats difference between the specified "
            "layouts.\nIf a baseline layout is not given, the analysis target "
            "is used."
    ),
    ("analyzediff", "diffa", "adiff", "analysediff"),
    cmd_analyze_diff
))

register_command(Command(
    CommandType.ANALYSIS,
    (
        "fulla[nalyze]diff [baseline_layout] <layout>: "
            "Like analyze but compares two layouts. Shows all tristroke "
            "categories",
        "Use analyzediff to see a more concise version."
    ),
    ("fullanalyzediff", "fullanalysediff", "fulladiff"),
    lambda args, s: cmd_analyze_diff(args, s, True)
))

def cmd_analyze_swap(args: list[str], s: Session, show_all: bool = False):

    if len(args) < 2:
        s.say("Usage: aswap [letter1 ... [with letter2 ...]]", gui_util.red)
        return
    
    baseline_layout = s.analysis_target
    if "with" in args:
        i = args.index("with")
        remap_ = remap.set_swap(args[:i], args[i+1:])
    else:
        remap_ = remap.cycle(*args)

    target_layout = layout.Layout(
        f"{baseline_layout.name}, {remap_}", 
        False, repr(baseline_layout))
    try:
        target_layout.remap(remap_)
    except KeyError as ke:
        s.say(f"Key '{ke.args[0]}' does not exist "
                f"in layout {baseline_layout.name}",
                gui_util.red)
        return
    
    s.say("Crunching the numbers >>>", gui_util.green)
    s.repl_win.refresh()

    if not show_all:
        s.output("\n" + target_layout.name + "\n"+ repr(target_layout))
        s.right_pane.refresh()

    cmd_analyze_diff_common(s, baseline_layout, target_layout, 
                        show_all, "fullaswap")
    
register_command(Command(
    CommandType.ANALYSIS,
    (
        "a[nalyze]swap <key1 key2> [...] [with ...]: Analyze a swap or cycle",
        "Same idea as analyzediff, but creates the edited layout on the fly. "
            "The edit is not saved."
    ),
    (
        "analyzeswap", "aswap", "analyseswap", 
        "acycle", "analyzecycle", "analysecycle"
    ),
    cmd_analyze_swap
))

register_command(Command(
    CommandType.ANALYSIS,
    (
        "fulla[nalyze]swap <key1 key2> [...] [with ...]: "
            "Analyze a swap or cycle. Shows all tristroke categories.",
        "Use analyzeswap to see a more concise version."
    ),
    (
        "fullanalyzeswap", "fullaswap", "fullanalyseswap", 
        "fullacycle", "fullanalyzecycle", "fullanalysecycle"
    ),
    lambda args, s: cmd_analyze_diff(args, s, True)
))

def cmd_stats(args: list[str], s: Session):
    if args:
        layout_name = " ".join(args)
        try:
            target_layout = layout.get_layout(layout_name)
        except FileNotFoundError:
            s.say(f"/layouts/{layout_name} was not found.", gui_util.red)
            return
    else:
        target_layout = s.analysis_target
    s.say("Crunching the numbers >>>", gui_util.green)
    s.repl_win.refresh()

    bstats, sstats, tstats, btop, stop = analysis.layout_stats_analysis(
        target_layout, s.corpus_settings)
    
    width = 46
    lwidth = 14
    output = ["", f"{'BIGRAMS ':-<{width}s}"]
    output.append(" "*lwidth+"Bigram           Skip-1-gram")
    bg_labels = (
        "Same finger",
        "Repeat",
        "Any stretch",
        "    Vertical",
        "    Lateral",
        "Alt hand",
        "Same hand"
    )
    bg_tags = ("sfb", "sfr", "asb", "vsb", "lsb", "ahb", "shb")
    for label, tag in zip(bg_labels, bg_tags):
        output.append(f"{label:<{lwidth}s}"
                        f"{bstats[tag]:6.2%}"
                        f" {' '.join(''.join(bg) for bg in btop[tag]):<8}"
                        f"  {sstats[tag]:6.2%}"
                        f" {' '.join(''.join(sg) for sg in stop[tag]):<8}")
    output.append(f"{'In/out ratio':<{lwidth}s}{bstats['inratio']:5.2f}"
                    f"           {sstats['inratio']:5.2f}")
    output.append("")
    output.append(f"{'TRIGRAMS ':-<{width}s}")
    output.append(f"")
    output.append(f"SFT excluded: {tstats['sft']:6.2%}")
    output.append(f"Total in/out: {tstats['inratio-trigram']:5.2f}")
    output.append(" "*lwidth+"Redir   Alt     Oneh    Roll")
    tg_labels = (
        "Good",
        "Any stretch",
        "SFS",
        "Weak fingers",
        "Total"
    )
    tg_tags = ("best", "stretch", "sfs", "weak", "total")
    for label, tag in zip(tg_labels, tg_tags):
        line = f"{label:<{lwidth}s}"
        for cat in ("redir", "alt", "oneh", "roll"):
            if f'{cat}-{tag}' in tstats.keys():
                line += f"{tstats[f'{cat}-{tag}']:6.2%}  "
            else:
                line += " "*8
        output.append(line)
    output.append(f"{'In/out ratio':<{lwidth+16}s}"
                    f"{tstats['inratio-oneh']:5.2f}"
                    f"   {sstats['inratio-roll']:5.2f}")
    s.output("\n".join(output))

    ymax = s.right_pane.getmaxyx()[0]
    row = ymax - 20

    for r, tag in enumerate(bg_tags, start=row):
        s.right_pane.addstr(r, lwidth+7, 
            f"{' '.join(''.join(bg) for bg in btop[tag]):<8}",
            curses.color_pair(gui_util.gray))
        s.right_pane.addstr(r, lwidth+24, 
            f"{' '.join(''.join(sg) for sg in stop[tag]):<8}",
            curses.color_pair(gui_util.gray))
    s.right_pane.refresh()

register_command(Command(
    CommandType.ANALYSIS,
    (
        "s[tats] [layout name]: More conventional frequency-only analysis",
        "Uses target layout if no args given."
    ),
    ("stats", "s"),
    cmd_stats
))

def cmd_dump(args: list[str], s: Session):
    if not args:
        s.say("Usage: dump <a[nalysis]|m[edians]>", gui_util.red)
        return
    if args[0] in ("a", "analysis"):
        return cmd_dump_analysis(args, s)
    elif args[0] in ("m", "medians"):
        return cmd_dump_medians(args, s)

def cmd_dump_analysis(args: list[str], s: Session):
        layout_file_list = scan_dir()
        if not layout_file_list:
            s.say("No layouts found in /layouts/", gui_util.red)
            return
        s.say(f"Analyzing {len(layout_file_list)} layouts...", gui_util.green)
        layouts = [layout.get_layout(name) for name in layout_file_list]
        
        s.right_pane.scroll(2)
        rownum = s.right_pane.getmaxyx()[0] - 1
        tristroke_display_names = []
        for cat in sorted(nstroke.all_tristroke_categories):
            try:
                tristroke_display_names.append(
                    nstroke.category_display_names[cat])
            except KeyError:
                tristroke_display_names.append(cat)
        bistroke_display_names = []
        for cat in sorted(nstroke.all_bistroke_categories):
            try:
                bistroke_display_names.append(
                    nstroke.category_display_names[cat])
            except KeyError:
                bistroke_display_names.append(cat)
        header = ["name"]
        for cat in tristroke_display_names:
            for colname in ("freq", "exact", "avg_ms", "ms"):
                header.append(f"tristroke-{cat}-{colname}")
        for cat in bistroke_display_names:
            for colname in ("freq", "exact", "avg_ms", "ms"):
                header.append(f"bistroke-{cat}-{colname}")
        filename = analysis.find_free_filename("output/dump-analysis", ".csv")
        with open(filename, "w", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(header)
            for i, lay in enumerate(layouts):
                tridata = analysis.layout_tristroke_analysis(
                    lay, s.typingdata_, s.corpus_settings)
                bidata = analysis.layout_bistroke_analysis(lay, s.typingdata_, 
                    s.corpus_settings)
                s.right_pane.addstr(rownum, 0, 
                    f"Analyzed {i+1}/{len(layouts)} layouts")
                s.right_pane.refresh()
                row = [lay.name]
                for cat in sorted(nstroke.all_tristroke_categories):
                    row.extend(tridata[cat])
                for cat in sorted(nstroke.all_bistroke_categories):
                    row.extend(bidata[cat])
                row.extend(repr(lay).split("\n"))
                w.writerow(row)
        curses.beep()
        s.output(f"Done\nSaved as {filename}", gui_util.green)

def cmd_dump_medians(args: list[str], s: Session):
    s.say("Crunching the numbers...", gui_util.green)
    tristroke_display_names = []
    for cat in sorted(nstroke.all_tristroke_categories):
        try:
            tristroke_display_names.append(nstroke.category_display_names[cat])
        except KeyError:
            tristroke_display_names.append(cat)
    header = ["trigram", "category", "ms_low", "ms_high", "ms_first", 
                "ms_second", "ms_total"]
    exacts = s.typingdata_.exact_tristrokes_for_layout(s.analysis_target)
    
    filename = analysis.find_free_filename("output/dump-catmedians", ".csv")
    with open(filename, "w", newline="") as csvfile:
        w = csv.writer(csvfile)
        w.writerow(header)
        for tristroke in exacts:
            row = [" ".join(s.analysis_target.to_ngram(tristroke))]
            if not row:
                continue
            row.append(nstroke.tristroke_category(tristroke))
            row.extend(sorted(s.typingdata_.tri_medians[tristroke][:2]))
            row.extend(s.typingdata_.tri_medians[tristroke])
            w.writerow(row)
    s.output(f"Done\nSaved as {filename}", gui_util.green)

register_command(Command(
    CommandType.ANALYSIS,
    (
        "dump <a[nalysis]|m[edians]>: Write some data to a csv",
        "analysis: full bistroke and tristroke statistics of each layout.\n"
            "medians: typing speeds of known trigrams (in the analysis target)"
    ),
    ("dump",),
    cmd_dump
))

def cmd_fingers(args: list[str], s: Session):
    if args:
        layout_name = " ".join(args)
        try:
            target_layout = layout.get_layout(layout_name)
        except FileNotFoundError:
            s.say(f"/layouts/{layout_name} was not found.", gui_util.red)
            return
    else:
        target_layout = s.analysis_target
    s.say("Crunching the numbers >>>", gui_util.green)
    
    finger_stats = analysis.finger_analysis(
        target_layout, s.typingdata_, s.corpus_settings)
    s.output(f"\nHand/finger breakdown for {target_layout}")
    print_finger_stats({k:v for k, v in finger_stats.items() if v[0]})

register_command(Command(
    CommandType.ANALYSIS,
    (
        "f[ingers] [layout name]: Hand/finger usage breakdown",
        "Uses analysis target if no layout given."
    ),
    ("fingers", "f"),
    cmd_fingers
))

def cmd_rank(args: list[str], s: Session):
    output = False
    if "output" in args:
        args.remove("output")
        output = True
    layout_file_list = scan_dir()
    if not layout_file_list:
        s.say("No layouts found in /layouts/", gui_util.red)
        return
    layouts: list[layout.Layout] = []
    if not args:
        args.append("") # match all layouts
    for name in layout_file_list:
        for str_ in args:
            if str_ in name:
                layouts.append(layout.get_layout(name))
                break
    s.say(f"Analyzing {len(layouts)} layouts >>>", gui_util.green)
    data = {}
    width = max(len(name) for name in layout_file_list)
    padding = 3
    col_width = width + 18 + 6
    header = "Layout" + " "*(width-3) + "avg_ms   wpm    exact"
    s.output(f"\n{header}")
    ymax, xmax = s.right_pane.getmaxyx()
    first_row = ymax - len(layouts) - 2
    if first_row < 1:
        first_row = 1
    s.right_pane.scroll(min(ymax-1, len(layouts) + 2))
    num_cols = (xmax + padding)//(col_width + padding)

    col_settings = (
        {"transform": math.sqrt, "worst": gui_util.MAD_z(5), 
            "best": gui_util.MAD_z(-5)}, # avg_ms
        {"transform": math.sqrt, "best": gui_util.MAD_z(5), 
            "worst": gui_util.MAD_z(-5)}, # exact
    )

    num_rows = ymax - first_row

    def print_row():
        nonlocal row
        nonlocal col
        s.right_pane.move(row, col)
        s.right_pane.clrtoeol()
        s.right_pane.addstr(
            row, col, f"{lay:{width}s}")
        s.right_pane.addstr( # avg_ms
            row, col+width+3, f"{data[lay][0]:6.2f}",
            pairs[0][lay])
        s.right_pane.addstr( # wpm
            row, col+width+12, f"{int(24000/data[lay][0]):3}",
            pairs[0][lay])
        s.right_pane.addstr( # exact
            row, col+width+18, f"{data[lay][1]:6.2%}",
            pairs[1][lay])
        row += 1

    # analyze all
    for lay in layouts:
        data[lay.name] = analysis.layout_speed(
            lay, s.typingdata_, s.corpus_settings)
        row = first_row
        sorted_ = list(sorted(data, key=lambda d: data[d][0]))
        displayed = {sorted_[i]: data[sorted_[i]] 
            for i in range(len(sorted_)) if i < num_rows*num_cols}
        pairs = gui_util.apply_scales(displayed, col_settings)
        col = 0
        # print ranking as of each step
        for lay in displayed:
            try:
                print_row()
            except curses.error: # maxed out first row
                row = first_row
                col += col_width + padding
                try:
                    s.right_pane.addstr(row-1, col, header)
                    print_row()
                except curses.error:
                    break
        s.right_pane.refresh()
    curses.beep()
    s.say(f"Ranking complete", gui_util.green)
    if output:
        header = ["name", "avg_ms", "exact"]
        filename = analysis.find_free_filename("output/ranking", ".csv")
        with open(filename, "w", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(header)
            for lay in layouts:
                row = [lay.name]
                row.extend(data[lay.name])
                row.extend(repr(lay).split("\n"))
                w.writerow(row)
        s.say(f"Saved ranking as {filename}", gui_util.green)

register_command(Command(
    CommandType.ANALYSIS,
    (
        "r[ank] [search term]: Rank all matching layouts by wpm\n"
            "r[ank] output [search term]: Dump results to a csv",
        "See who does best in the signature trialyzer metric.\n"
            "Add a search string to restrict to layouts matching that string."
    ),
    ("rank", "r"),
    cmd_rank
))

def cmd_rt(args: list[str], s: Session):
    reverse_opts = {"min": False, "max": True}
    analysis_opts = {"freq": 0, "exact": 1, "avg_ms": 2, "ms": 3}
    try:
        reverse_ = reverse_opts[args[0]]
        sorting_col = analysis_opts[args[1]]
    except (KeyError, IndexError):
        s.say("Usage: rt <min|max> <freq|exact|avg_ms|ms> [category]",
            gui_util.red)
        return
    try:
        category = nstroke.parse_category(args[2])
        if category is None:
            return
    except IndexError:
        category = ""
    category_name = nstroke.category_display_name(category)

    layout_file_list = scan_dir()
    if not layout_file_list:
        s.say("No layouts found in /layouts/", gui_util.red)
        return
    s.say(f"Analyzing {len(layout_file_list)} layouts >>>", gui_util.green)
    width = max(len(name) for name in layout_file_list)
    padding = 3
    header = (f"Ranking by tristroke category: {category_name}, "
        f"{args[0]} {args[1]} first", 
        "Layout" + " "*(width-1) + "freq    exact   avg_ms      ms")
    headerjoin = '\n'.join(header) # '\n' not allowed inside f-string
    s.output(f"\n{headerjoin}")
    col_width = width + 29 + 6
    ymax, xmax = s.right_pane.getmaxyx()
    first_row = ymax - len(layout_file_list) - 3
    if first_row < 2:
        first_row = 2
    s.right_pane.scroll(min(ymax-2, len(layout_file_list) + 1))
    s.right_pane.refresh()
    num_cols = (xmax + padding)//(col_width + padding)
    layouts = [layout.get_layout(name) for name in layout_file_list]
    num_rows = ymax - first_row

    data = {}

    col_settings = [ # for colors
        {"transform": math.sqrt, "best": gui_util.MAD_z(5), 
            "worst": gui_util.MAD_z(-5)}, # freq
        {"transform": math.sqrt, "best": gui_util.MAD_z(5), 
            "worst": gui_util.MAD_z(-5)}, # exact
        {"worst": gui_util.MAD_z(5), 
            "best": gui_util.MAD_z(-5)}, # avg_ms
        {"transform": math.sqrt, "worst": gui_util.MAD_z(5), 
            "best": gui_util.MAD_z(-5)}, # ms
    ]
    col_settings_inverted = col_settings.copy()
    col_settings_inverted[0] = col_settings_inverted[3]

    def print_row():
        nonlocal row
        nonlocal col
        s.right_pane.move(row, col)
        s.right_pane.clrtoeol()
        s.right_pane.addstr(
            row, col, f"{rowname:{width}s}   ")
        s.right_pane.addstr( # freq
            row, col+width+3, f"{rows[rowname][0]:>6.2%}",
            pairs[0][rowname])
        s.right_pane.addstr( # exact
            row, col+width+12, f"{rows[rowname][1]:>6.2%}",
            pairs[1][rowname])
        s.right_pane.addstr( # avg_ms
            row, col+width+21, f"{rows[rowname][2]:>6.1f}",
            pairs[2][rowname])
        s.right_pane.addstr( # ms
            row, col+width+29, f"{rows[rowname][3]:>6.2f}",
            pairs[3][rowname])
        row += 1
    
    for lay in layouts:
        data[lay.name] = analysis.layout_tristroke_analysis(
            lay, s.typingdata_, s.corpus_settings)
        row = first_row
        col = 0
        
        # color freq by whether the category is faster than total
        try:
            this_avg = statistics.fmean(
                data[layname][category][2] for layname in data)
            total_avg = statistics.fmean(
                data[layname][""][2] for layname in data)
            invert = this_avg > total_avg
        except statistics.StatisticsError:
            invert = False
        names = list(sorted(
            data, key=lambda name: data[name][category][sorting_col], 
            reverse=reverse_))
        rows = {name: data[name][category] 
            for i, name in enumerate(names) if i < num_rows*num_cols}
        if invert:
            pairs = gui_util.apply_scales(
                rows, col_settings_inverted)    
        else:
            pairs = gui_util.apply_scales(rows, col_settings)

        # printing
        for rowname in rows:
            try:
                print_row()
            except curses.error:
                row = first_row
                col += col_width + padding
                try:
                    # right_pane.addstr(row-2, col, header[0])
                    s.right_pane.addstr(row-1, col, header[1])
                    print_row()
                except curses.error:
                    break
        s.right_pane.refresh()
    curses.beep()
    s.say(f"Ranking complete", gui_util.green)

register_command(Command(
    CommandType.ANALYSIS,
    (
        "rt <min|max> <freq|exact|avg_ms|ms> [category]: "
            "Rank by tristroke statistic.",
        "The tristroke category defaults to \"\" (all tristrokes) if not "
            "specified."
    ),
    ("rt",),
    cmd_rt
))

def cmd_bistroke(args: list[str], s: Session):
    if not args:
        s.say("Crunching the numbers >>>", gui_util.green)
        s.right_pane.clear()
        print_stroke_categories(
            s.typingdata_.bistroke_category_data(s.analysis_target))
    else:
        s.say("Individual bistroke stats are"
            " not yet implemented", gui_util.red)
        
register_command(Command(
    CommandType.ANALYSIS,
    (
        "bs [bistroke]: Show specified/all bistroke stats",
    ),
    ("bistroke", "bs"),
    cmd_bistroke
))

def cmd_tristroke(args: list[str], s: Session):
    if not args:
        s.say("Crunching the numbers >>>", gui_util.green)
        s.right_pane.clear()
        data = s.typingdata_.tristroke_category_data(s.analysis_target)
        s.output("Category                       ms    n     possible")
        s.analysis_target.preprocessors["counts"].join()
        print_stroke_categories(data, s.analysis_target.counts)
    else:
        s.say("Individual tristroke stats are"
            " not yet implemented", gui_util.red)

register_command(Command(
    CommandType.ANALYSIS,
    (
        "ts [tristroke]: Show specified/all tristroke stats",
    ),
    ("tristroke", "ts"),
    cmd_tristroke
))

def cmd_speeds_file(args: list[str], s: Session):
    if not args:
        s.speeds_file = "default"
    else:
        s.speeds_file = " ".join(args)
    s.typingdata_ = TypingData(s.speeds_file)
    s.say(f"Set active speeds file to /data/{s.speeds_file}.csv",
            gui_util.green)
    if not os.path.exists(f"data/{s.speeds_file}.csv"):
        s.say("The new file will be written upon save", gui_util.blue)
    s.save_settings()

register_command(Command(
    CommandType.DATA,
    (
        "df [filename]: Set typing data file, or use default",
        "The selected file will be used to store typing test data, and will "
            "supply data for analysis. \nThe .csv suffix will be appended to "
            "the filename you give.\nDefaults to /data/default.csv."
    ),
    ("datafile", "speedsfile", "df"),
    cmd_speeds_file
))

def cmd_improve(args: list[str], s: Session):
    pins = []
    if "pin" in args:
        while True:
            token = args.pop()
            if token == "pin":
                break
            else:
                pins.append(token)
    if args:
        layout_, _ = extract_layout_front(args)
        if layout_ is None:
            s.say(f"/layouts/{' '.join(args)} was not found", gui_util.red)
            return
        target_layout = layout_
    else:
        target_layout = s.analysis_target
    s.say("Using steepest ascent... >>>", gui_util.green)
    
    initial_score = analysis.layout_speed(
        target_layout, s.typingdata_, s.corpus_settings)[0]
    s.output(f"\nInitial layout: avg_ms = {initial_score:.4f}\n"
        + limited_repr(target_layout))
    
    num_swaps = 0
    optimized = target_layout
    pins.extend(target_layout.get_board_keys()[0].values())
    for optimized, score, remap_ in analysis.steepest_ascent(
        target_layout, s, pins
    ):
        num_swaps += 1
        repr_ = repr(optimized)
        s.output(f"Edit #{num_swaps}: avg_ms = {score:.4f} ({remap_})"
            f"\n{repr_}", )
    curses.beep()
    s.output(f"Local optimum reached", gui_util.green)
    
    if optimized is not target_layout:
        with open(f"layouts/{optimized.name}", "w") as file:
                file.write(repr_)
        s.output(
            f"Saved new layout as {optimized.name}\n"
            "Set as analysis target",
            gui_util.green)
        # reload from file in case
        layout.Layout.loaded[optimized.name] = layout.Layout(
            optimized.name)
        s.analysis_target = layout.get_layout(optimized.name)
        s.save_settings()

register_command(Command(
    CommandType.EDITING,
    (
        "i[mprove]|ascend [layout name] [pin <keys>]: "
            "Optimize using steepest ascent swaps",
        "Uses the target layout if none is given.\n"
            "Considers all allowed swaps (adhering to the constraintmap) "
            "and picks the best, repeating until reaching a local optimum in "
            "layout tristroke speed. Saves the result.\n"
            "Automatically pins default_keys which are part of the board, "
            "such as shift."
    ),
    ("improve", "ascend", "i"),
    cmd_improve
))

def cmd_si(args: list[str], s: Session):
    num_iterations = 10 # reasonable default
    for item in args:
        try:
            num_iterations = int(item)
            args.remove(item)
            break
        except ValueError:
            continue        
    pins = []
    if "pin" in args:
        while True:
            token = args.pop()
            if token == "pin":
                break
            else:
                pins.append(token)
    if args:
        layout_, _ = extract_layout_front(args)
        if layout_ is not None:
            target_layout = layout_
        else:
            s.say(f"/layouts/{' '.join(args)} was not found", gui_util.red)
            return
    else:
        target_layout = analysis_target
    pins.extend(target_layout.get_board_keys()[0].values())
    pin_positions = {key: target_layout.positions[key] for key in pins}
    try: # load existing best if present
        working_lay = layout.Layout(target_layout.name + "-best", False)
    except FileNotFoundError:
        working_lay = layout.Layout(target_layout.name, False)
    for key in pin_positions:
        if pin_positions[key] != working_lay.positions[key]:
            working_lay = layout.Layout(target_layout.name, False)
            break

    # ideally this wouldn't be necessary, but pins exceeding the pinky cap
    # would cause trouble. Maybe improve this in the future
    # finger_freqs = working_lay.frequency_by_finger()
    # initial_pinky_freq = max(
    #     finger_freqs[Finger.RP], finger_freqs[Finger.LP])
    # if pinky_cap < initial_pinky_freq:
    #     pinky_cap = initial_pinky_freq

    s.say("Shuffling & ascending... >>>", gui_util.green)
    
    best_score = analysis.layout_speed(
            working_lay, s.typingdata_, s.corpus_settings)[0]
    s.output(f"Initial best: avg_ms = {best_score:.4f}\n"
            + limited_repr(working_lay))
    
    lfreqs = s.target_corpus.key_counts
    total_lfreq = sum(lfreqs[key] for key in working_lay.positions
        if key in lfreqs)
    for key in lfreqs:
        lfreqs[key] /= total_lfreq

    def shuffle_source():
        return s.constraintmap_.random_legal_swap(
            working_lay, lfreqs, pins)
    
    name = working_lay.name
    if not name.endswith("-best"):
        name += "-best"
    name = analysis.find_free_filename(name)

    for iteration in range(num_iterations):
        working_lay.constrained_shuffle(shuffle_source)
        num_shuffles = 0
        while (not s.constraintmap_.is_layout_legal(working_lay, lfreqs)):
            working_lay.constrained_shuffle(shuffle_source)
            num_shuffles += 1
            if num_shuffles >= 100000:
                s.output("Unable to satisfy constraintmap after shuffling"
                    f" {num_shuffles} times. Constraintmap/pins might be"
                    " too strict?", gui_util.red)
                return
        initial_score = analysis.layout_speed(
            working_lay, s.typingdata_, s.corpus_settings)[0]
        s.output(f"\nShuffle/Attempt {iteration}\n"
            f"Initial shuffle: avg_ms = {initial_score:.4f}\n"
            + limited_repr(working_lay))
        
        num_swaps = 0
        optimized = working_lay
        for optimized, score, remap_ in analysis.steepest_ascent(
            working_lay, s,pins, "-best"
        ):
            num_swaps += 1
            repr_ = limited_repr(optimized)
            s.output(f"Edit #{iteration}.{num_swaps}: avg_ms = {score:.4f}"
                f" ({remap_})\n{repr_}")
        s.output(f"Local optimum reached", gui_util.green)
        
        if optimized is not working_lay and score < best_score:
            s.output(
                f"New best score of {score:.4f}\n"
                f"Saved as layouts/{name}", 
                gui_util.green)
            best_score = score
            with open(f"layouts/{name}", "w") as file:
                    file.write(repr_)
    s.output("\nSet best as analysis target",
        gui_util.green)
    # reload from file in case
    curses.beep()
    try:
        layout.Layout.loaded[optimized.name] = layout.Layout(
            optimized.name)
        analysis_target = layout.get_layout(optimized.name)
        s.save_settings()
    except FileNotFoundError: # no improvement found
        return
    
register_command(Command(
    CommandType.EDITING,
    (
        "si [layout name] [n] [pin <keys>]: "
            "Shuffle and run steepest ascent n times, saving the best",
        "Uses the target layout if none is given.\n"
            "See improve for details - this works the same, but shuffles "
            "first, and only keeps the best of n attempts."
    ),
    ("shuffleimprove", "si", "shotgunimprove"),
    cmd_si
))

def cmd_anneal(args: list[str], s: Session):
    num_iterations = 10000 # reasonable default
    for item in args:
        try:
            num_iterations = int(item)
            args.remove(item)
            break
        except ValueError:
            continue
    pins = []
    if "pin" in args:
        while True:
            token = args.pop()
            if token == "pin":
                break
            else:
                pins.append(token)
    if args:
        layout_, _ = extract_layout_front(args)
        if layout_ is not None:
            target_layout = layout_
        else:
            s.say(f"/layouts/{' '.join(args)} was not found", 
                gui_util.red)
            return
    else:
        target_layout = analysis_target

    pins.extend(target_layout.get_board_keys()[0].values())
    s.say("Annealing... >>>", gui_util.green)

    initial_score = analysis.layout_speed(
        target_layout, s.typingdata_, s.corpus_settings)[0]
    s.output(
        f"Initial score: avg_ms = {initial_score:.4f}\n"
        + limited_repr(target_layout))
    
    last_time = -1
    optimized = target_layout
    convergence_chain = 0
    convergence_epsilon = 0.01
    convergence_threshold = 400
    for optimized, i, temperature, delta, score, remap_ in analysis.anneal(
        target_layout, s, pins, "-annealed", num_iterations
    ):
        if abs(delta) > convergence_epsilon:
            convergence_chain = 0
        else:
            convergence_chain += 1
        if convergence_chain > convergence_threshold:
            s.output(f"Early convergence detected: "
                    f"({convergence_threshold} steps with "
                    f"delta < {convergence_epsilon})")
            break
        current_time = time.perf_counter()
        if current_time - last_time < 0.5:
            continue # dont spam the console by printing
        last_time = current_time
        repr_ = repr(optimized)
        s.output(
            f"{i/num_iterations:.2%} progress, "
            f"temperature = {temperature:.4f}, delta = {delta:.4f}\n"
            f"avg_ms = {score:.4f}, last edit: {remap_}\n"
            f"{repr_}")
    i = 1
    path_ = analysis.find_free_filename(f"layouts/{optimized.name}")
    with open(path_, "w") as file:
            file.write(repr(optimized))
    optimized.name = path_[8:]
    curses.beep()
    s.output(
        f"Annealing complete\nSaved as {path_}"
        "\nSet as analysis target", 
        gui_util.green)
    layout.Layout.loaded[optimized.name] = layout.Layout(
        optimized.name)
    analysis_target = layout.get_layout(optimized.name)
    s.save_settings()

register_command(Command(
    CommandType.EDITING,
    (
        "anneal [layout name] [n] [pin <keys>]: "
            "Optimize with simulated annealing",
        "Uses the target layout if none is given.\n"
            "Considers random allowed edits (adhering to the constraintmap) "
            "and their effect on layout tristroke speed. Gets more picky over "
            "time about which edits it accepts. This is guided by a number "
            "called the temperature, which automatically decreases with "
            "time.\nFinishes after n steps (defaults to 10,000), or when "
            "early convergence is detected. Saves the result.\n"
            "Automatically pins default_keys which are part of the board, "
            "such as shift."
    ),
    ("anneal"),
    cmd_anneal
))

def cmd_corpus(args: list[str], s: Session):
    if not args:
        s.say("\n".join((
            "Usage: (note the several subcommands)",
            "corpus <filename> [space_key [shift_key [shift_policy]]]: "
                "Set corpus to /corpus/filename and set rules",
            "corpus space_key [key]: Set space key",
            "corpus shift_key [key]: Set shift key",
            "corpus shift_policy <once|each>:"
                " Set policy for consecutive capital letters",
            "corpus precision <n|full>: "
                "Set analysis to use the top n trigrams, or all",
        )), gui_util.red)
        return
        
    fields = ("space_key", "shift_key", "shift_policy", "precision")
    if args[0] not in fields:
        if not os.path.exists(f"corpus/{args[0]}"):
            s.say(f"/corpus/{args[0]} was not found.", gui_util.red)
            return
        s.corpus_settings["filename"] = args.pop(0)
        if len(args) >= 3:
            if args[2] not in ("once, each"):
                s.say("shift_policy must be \"once\" or \"each\"",
                    gui_util.red)
                return
        for field, input_ in zip(fields, args[:3]):
            s.corpus_settings[field] = input_ # early exit if <3 given
        s.message("Corpus settings updated", gui_util.green)
    else:
        if len(args) < 2:
            args.append("") # user wants to set key to the empty string
        if args[0] == "shift_policy" and args[1] not in ("once", "each"):
            s.say("shift_policy must be \"once\" or \"each\"", gui_util.red)
            return
        elif args[0] == "precision":
            try:
                args[1] = int(args[1])
            except ValueError:
                if args[1] == "full":
                    args[1] = 0
                else:
                    s.say("Precision must be an integer or \"full\"", 
                        gui_util.red)
                    return
        s.corpus_settings[args[0]] = args[1]
        if args[0] == "precision":
            s.target_corpus.set_precision(args[1])
            s.say(f"Set trigram precision to {args[1]} "
                f"({s.target_corpus.trigram_completeness:.3%})", 
                gui_util.green)
        else:
            s.say(f"Set {args[0]} to {args[1] if args[1] else 'None'}",
                gui_util.green)
    s.save_settings()
    s.target_corpus = s.analysis_target.get_corpus(s.corpus_settings)

register_command(Command(
    CommandType.DATA,
    (
        "corpus <filename> [space_key [shift_key [shift_policy]]]: "
                "Set corpus to /corpus/filename and set rules\n"
            "corpus space_key [key]: Set space key\n"
            "corpus shift_key [key]: Set shift key\n"
            "corpus shift_policy <once|each>:"
                " Set policy for consecutive capital letters\n"
            "corpus precision <n|full>: "
                "Set analysis to use the top n trigrams, or all\n",
        "Space and shift keys are often changed if you want to try analysis "
            "that takes into account those keys being pressed with particular "
            "fingers. For example, trialyzer defaults to splitting the "
            "spacebar into space_l and space_r, one for each thumb.\n"
            "For shift_policy, once means that when "
            "consecutive capital letters occur, shift is only pressed once "
            "before the first letter. each means shift is pressed before "
            "each letter."
    ),
    ("corpus",),
    cmd_corpus
))

def cmd_constraintmap(args: list[str], s: Session):
    try: 
        s.constraintmap_ = constraintmap.get_constraintmap(
            " ".join(args))
        s.save_settings()
        s.say(f"Set constraintmap to {s.constraintmap_.name}", gui_util.green)
    except FileNotFoundError:
        s.say(f"/constraintmaps/{' '.join(args)} was not found.",
            gui_util.red)
    
register_command(Command(
    CommandType.EDITING,
    (
        "cm|constraintmap [constraintmap name]: Set constraintmap",
        "Refers to a constraintmap in /constraintmaps/"
    ),
    ("constraintmap", "cm"),
    cmd_constraintmap
))

def cmd_help(args: list[str], s: Session):
    help_text = [
        "",
        "",
        "Command <required thing> [optional thing] option1|option2",
    ]

    if not args:
        help_text = cmd_help_intro(help_text)
    else:
        try:
            cat = CommandType[args[0].upper()]
            help_text = cmd_help_cat(help_text, cat)
        except KeyError:
            cmd: Command = by_name.get(args[0], None)
            if cmd is None:
                s.say("Unrecognized command", gui_util.red)
                return
            help_text = cmd_help_cmd(help_text, cmd)

    ymax = s.right_pane.getmaxyx()[0]
    for line in help_text:
        if ":" in line:
            white_part, rest = line.split(":", 1)
            white_part += ":"
            rest_pos = len(white_part)
            s.right_pane.addstr(ymax-1, 0, white_part)
            s.right_pane.addstr(ymax-1, rest_pos, rest, 
                                curses.color_pair(gui_util.blue))
        else:
            s.right_pane.addstr(ymax-1, 0, line)
        s.right_pane.scroll(1)
    s.right_pane.refresh()

def cmd_help_intro(l: list[str]):
    l.extend((
        "-----Command categories-----",
        "There are a lot of commands, so let's not list them all together.",
        "Use help <category> to list commands in one of these categories:",
    ))
    l.extend(cat.name for cat in CommandType)
    l.extend((
        "-----Multiple and repeating commands-----",
        "Precede with a number to execute the command n times.",
        "For example, \"10 anneal QWERTY\".",
        "\".\" is shorthand for \"the last thing entered\".",
        "For example, \"2 .\".",
    ))
    return l

def cmd_help_cat(l: list[str], cat: CommandType):
    l.append(f"Commands in category {cat.name}:")
    l.extend(cmd.help[0] for cmd in sorted(
        (cmd for cmd in commands if cmd.type == cat), 
        key=lambda c: c.names[0]))
    l.append("Use help <command> to view per-command help")
    return l

def cmd_help_cmd(l: list[str], cmd: Command):
    l.append("")
    l.extend(cmd.help)
    l.append(f"\nAliases: {', '.join(cmd.names)}")
    return l

register_command(Command(
    CommandType.GENERAL,
    ("help [category or command]: List or explain commands",),
    ("help", "h"),
    cmd_help
))



# Helper functions

def print_stroke_categories(s: Session, data: dict, counts: dict = None):
    s.right_pane.scroll(len(data))
    ymax = s.right_pane.getmaxyx()[0]
    row = ymax - len(data)

    p_pairs = {} # proportion completed
    s_pairs = {} # speeds
    c_pairs = {} # total count

    # setup & calcs
    if counts:
        # log causes better usage of the gradient
        log_counts = {cat: math.log(counts[cat]) 
            if counts[cat] else 0 for cat in counts}
        cmin = min(filter(None, log_counts.values()))
        cmax = max(log_counts.values())
        completion = {}
        for category in data:
            if data[category][1] > 0 and counts[category]:
                # sqrt makes smaller differences more visible
                completion[category] = math.sqrt(
                    data[category][1]/counts[category])
            else:
                completion[category] = 0
        madm5 = gui_util.MAD_z(-5.0)
        mad5 = gui_util.MAD_z(5.0)
        for category in data:
            p_pairs[category] = curses.color_pair(gui_util.color_scale(
                madm5(filter(None, completion.values())), 
                mad5(completion.values()),
                completion[category], True))
            c_pairs[category] = curses.color_pair(gui_util.color_scale(
                cmin, cmax, log_counts[category], True))
    else:
        for category in data:
            p_pairs[category] = curses.color_pair(0)

    for category in data:
        s_pairs[category] = curses.color_pair(gui_util.color_scale(
            max(val[0] for val in data.values()),
            min(val[0] for val in data.values()), 
            data[category][0]))
    
    # printing
    for category in sorted(data):
        category_name = (nstroke.category_display_names[category] 
            if category in nstroke.category_display_names else category)
        pad_char = " "
        if category.endswith(".") or not category:
            category_name += " (total)"
            pad_char = "-"
        if not category.startswith("."):
            if "." not in category_name:
                pad_char = "-"
                category_name += " "
        s.right_pane.addstr(
            row, 0, ("{:" + pad_char + "<26}").format(category_name))
        s.right_pane.addstr(
            row, 27, "{:>6.1f}".format(float(data[category][0])),
            s_pairs[category])
        s.right_pane.addstr(
            row, 36, "{:< 6}".format(data[category][1]),
            p_pairs[category])
        if counts:
            s.right_pane.addstr(
                row, 43, "/{:<6}".format(counts[category]), 
                c_pairs[category])
        row += 1
    
    s.right_pane.refresh()

def print_analysis_stats(s: Session, stats: dict, header_line: str, 
                         diff_mode: bool = False):
    # colors
    if diff_mode:
        col_settings = (
            {"transform": gui_util.odd_sqrt, "worst": gui_util.neg_extreme, "best": gui_util.extreme,
                "scale_filter": lambda val: val != stats[""][0]},
            {"transform": gui_util.odd_sqrt, "worst": gui_util.neg_extreme, "best": gui_util.extreme},
            {"worst": gui_util.extreme, "best": gui_util.neg_extreme},
            {"transform": gui_util.odd_sqrt, "worst": gui_util.extreme, "best": gui_util.neg_extreme,
                "scale_filter": lambda val: val != stats[""][3]},
        )
    else:
        col_settings = (
            {"transform": gui_util.odd_sqrt, 
                "scale_filter": lambda val: val != stats[""][0]},
            {"transform": gui_util.odd_sqrt},
            {"worst": max, "best": min},
            {"transform": gui_util.odd_sqrt, "worst": max, "best": min,
                "scale_filter": lambda val: val != stats[""][3]},
        )
    pairs = gui_util.apply_scales(stats, col_settings)

    gui_util.insert_line_bottom(header_line, s.right_pane)
    s.right_pane.scroll(len(stats))
    ymax = s.right_pane.getmaxyx()[0]
    row = ymax - len(stats)

    # printing
    s = '+' if diff_mode else ''
    for category in sorted(stats):
        category_name = (nstroke.category_display_names[category] 
            if category in nstroke.category_display_names else category)
        pad_char = " "
        if category.endswith(".") or not category:
            category_name += " (total)"
            pad_char = "-"
        if not category.startswith("."):
            if "." not in category_name:
                pad_char = "-"
                category_name += " "
        s.right_pane.addstr( # category name
            row, 0, ("{:" + pad_char + "<26}").format(category_name))
        s.right_pane.addstr( # freq
            row, 27, f"{stats[category][0]:>{s}6.2%}",
            pairs[0][category])
        s.right_pane.addstr( # known_freq
            row, 36, f"{stats[category][1]:>{s}6.2%}",
            pairs[1][category])
        s.right_pane.addstr( # speed
            row, 45, f"{stats[category][2]:>{s}6.1f}",
            pairs[2][category])
        s.right_pane.addstr( # contrib
            row, 53, f"{stats[category][3]:>{s}6.2f}",
            pairs[3][category])
        row += 1
    
    s.right_pane.refresh()

def print_finger_stats(s: Session, stats: dict):
    # colors
    col_settings = (
        {"transform": math.sqrt},
        {"transform": math.sqrt},
        {"transform": math.sqrt},
        {"worst": max, "best": min},
        {"transform": math.sqrt, "worst": max, "best": min},
        )
    pairs = gui_util.apply_scales(stats, col_settings)

    categories = []
    categories.extend(
        name for name in nstroke.hand_names.values() if name in stats)
    categories.extend(
        name for name in nstroke.finger_names.values() if name in stats)
    categories.extend(
        finger.name for finger in Finger if finger.name in stats)

    longest = len(max(categories, key=len)) + 2

    header_line = (
            "-" * (longest-6) +
            " letter stats | tristroke stats ----------------"
            "\nCategory" + " " * (longest-8) + 
            "   freq |   freq    exact   avg_ms      ms"
    )

    gui_util.insert_line_bottom(header_line, s.right_pane)
    s.right_pane.scroll(len(stats))
    ymax = s.right_pane.getmaxyx()[0]
    row = ymax - len(stats)

    # printing
    for category in categories:
        s.right_pane.addstr( # category name
            row, 0, f"{category:<{longest}}")
        s.right_pane.addstr( # lfreq
            row, longest+1, f"{stats[category][0]:>6.2%}",
            pairs[0][category])
        s.right_pane.addstr(row, longest+8, "|")
        s.right_pane.addstr( # tfreq
            row, longest+10, f"{stats[category][1]:>6.2%}",
            pairs[1][category])
        s.right_pane.addstr( # known
            row, longest+19, f"{stats[category][2]:>6.2%}",
            pairs[2][category])
        s.right_pane.addstr( # avg_ms
            row, longest+28, f"{stats[category][3]:>6.1f}",
            pairs[3][category])
        s.right_pane.addstr( # ms
            row, longest+36, f"{stats[category][4]:>6.2f}",
            pairs[4][category])
        row += 1
    
    s.right_pane.refresh()

def scan_dir(path: str = "layouts/.", exclude: str = "."):
    file_list = []
    with os.scandir(path) as files:
        for file in files:
            if exclude not in file.name and file.is_file():
                file_list.append(file.name)
    return file_list

def limited_repr(l: layout.Layout, lines: int = 6):
    r = repr(l).splitlines()
    if len(r) > lines:
        r = r[:lines] 
        r.append("...See file for full spec")
    return "\n".join(r)

def extract_layout_front(tokens: Iterable[str], require_full: bool = False):
    """Attempts to find a named layout by joining the tokens with spaces. 
    Returns the layout and remaining tokens. If require_full is set, the
    layout name must take up the entire token."""
    tokens = list(tokens)
    remainder = []
    while tokens:
        try:
            layout_ = layout.get_layout(" ".join(tokens))
            return layout_, remainder
        except FileNotFoundError:
            if require_full:
                return None, tokens
            else:
                remainder.insert(0, tokens.pop())
    return None, remainder
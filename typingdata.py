# Planned as a way to consolidate medians, bistroke/tristroke speed data, etc
# Goals:
#   - Cache all tristroke medians/other data in one place
#       - Compute new ones when needed
#   - Update when csvdata is updated
#       - dedicated add/remove functions clear affected data from caches
#       - or mutate just the relevant data?
#       - nah too much work for now, just rudimentary cache clearing
#       - may do more fancy things later

import csv
import functools
import itertools
import operator
import statistics
from collections import defaultdict
from typing import Callable

import layout
import nstroke
from board import Coord
from fingermap import Finger
from layout import Layout
from nstroke import Nstroke, Tristroke

def _find_existing_cached(cache, layout_: Layout):
    """Finds a cached property by looking up cache[layout_.name]. Will 
    alternatively find cache[other_layout.name] if other_layout has the same 
    tristrokes as layout_. Returns None if none found."""
    if layout_.name in cache:
        return cache[layout_.name]
    else:
        for other_name in cache:
            try:
                other_layout = layout.get_layout(other_name)
            except OSError: 
                # temporary layouts may exist from si command, etc
                continue
            if layout_.has_same_tristrokes(other_layout):
                return cache[other_name]
    return None

class TypingData:
    def __init__(self, csv_filename: str) -> None:
        """Raises OSError if data/csv_filename.csv not found."""
        self.csv_filename = csv_filename
        
        # csv_data[tristroke] -> ([speeds_01], [speeds_12])
        self.csv_data: dict[Tristroke, tuple[list, list]]
        self.csv_data = defaultdict(lambda: ([], []))

        try:
            self.load_csv()
        except OSError:
            pass # just let the data be written upon save

        # medians[tristroke] -> (speed_01, speed_12, speed_02)
        self.tri_medians: dict[Tristroke, tuple[float, float, float]] 
        self.tri_medians = {}

        # exact_tristrokes[layout_name] -> set of tristrokes
        self.exact_tristrokes: dict[str, set[Tristroke]] = {}

        # bicatdata[layout_name][category] -> (speed, num_samples)
        self.bicatdata: dict[str, dict[str, tuple[float, int]]] = {}

        # tricatdata[layout_name][category] -> (speed, num_samples)
        self.tricatdata: dict[str, dict[str, tuple[float, int]]] = {}

        # tribreakdowns[layout_name][category][bistroke] 
        #     -> (speed, num_samples)
        self.tribreakdowns: dict[str, dict[str, dict[str, tuple(float, int)]]]
        self.tribreakdowns = {}

        # speed_funcs[layout_name] -> speed_func(tristroke) -> (speed, exact)
        self.speed_funcs: dict[str, Callable[[Tristroke], tuple[float, bool]]]
        self.speed_funcs = {}

    def refresh(self):
        """Clears caches; they will be repopulated when needed"""
        for cache in (
                self.tri_medians, self.exact_tristrokes, self.bicatdata, 
                self.tricatdata, self.tribreakdowns, self.speed_funcs):
            cache.clear()
    
    def load_csv(self):
        with open(f"data/{self.csv_filename}.csv", "r", 
                newline="") as csvfile:
            reader = csv.DictReader(csvfile, restkey="speeds")
            for row in reader:
                if "speeds" not in row:
                    continue
                fingers = tuple(
                    Finger[row[f"finger{n}"]] for n in range(3))
                coords = tuple(
                    (Coord(float(row[f"x{n}"]), float(row[f"y{n}"]))
                        for n in range(3)))
                tristroke = Tristroke(row["note"], fingers, coords)
                # there may be multiple rows for the same tristroke
                for i, time in enumerate(row["speeds"]):
                    self.csv_data[tristroke][i%2].append(float(time))
    
    def save_csv(self):
        header = [
            "note", "finger0", "finger1", "finger2",
            "x0", "y0", "x1", "y1", "x2", "y2"
        ]
        with open(f"data/{self.csv_filename}.csv", "w", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(header)
            for tristroke in self.csv_data:
                if (not self.csv_data[tristroke] 
                        or not self.csv_data[tristroke][0]):
                    continue
                row: list = self._start_csv_row(tristroke)
                row.extend(itertools.chain.from_iterable(
                    zip(self.csv_data[tristroke][0], 
                        self.csv_data[tristroke][1])))
                w.writerow(row)
    
    def _start_csv_row(self, tristroke: Tristroke):
        """Order of returned data: note, fingers, coords"""
        
        result = [tristroke.note]
        result.extend(f.name for f in tristroke.fingers)
        result.extend(itertools.chain.from_iterable(tristroke.coords))
        return result

    def calc_medians_for_tristroke(self, tristroke: Tristroke):
        """Returns (speed_01, speed_12, speed_02) if relevant csv data exists,
        otherwise returns None.
        """
        if tristroke in self.tri_medians:
            return self.tri_medians[tristroke]

        speeds_01: list[float] = []
        speeds_12: list[float] = []
        if tristroke in self.csv_data:
            speeds_01.extend(self.csv_data[tristroke][0])
            speeds_12.extend(self.csv_data[tristroke][1])
        else:
            for csv_tristroke in self.csv_data:
                if csv_tristroke.fingers == tristroke.fingers:
                    if nstroke.compatible(tristroke, csv_tristroke):
                        speeds_01.extend(self.csv_data[csv_tristroke][0])
                        speeds_12.extend(self.csv_data[csv_tristroke][1])
        speeds_02: list[float] = map(operator.add, speeds_01, speeds_12)
        try:
            data = (
                statistics.median(speeds_01),
                statistics.median(speeds_12),
                statistics.median(speeds_02)
            )
            self.tri_medians[tristroke] = data
            return data
        except statistics.StatisticsError:
            return None

    def exact_tristrokes_for_layout(self, layout_: Layout):
        """Uses cached set if it exists. Otherwise, builds the set from
        typing data and ensures the corresponding medians are precalculated
        in self.medians.
        """
        existing = _find_existing_cached(self.exact_tristrokes, layout_)
        if existing is not None:
            return existing

        result: set[Tristroke] = set()
        for csv_tristroke in self.csv_data:
            for layout_tristroke in layout_.nstrokes_with_fingers(
                    csv_tristroke.fingers):
                if nstroke.compatible(csv_tristroke, layout_tristroke):
                    self.calc_medians_for_tristroke(layout_tristroke) # cache
                    result.add(layout_tristroke)

        self.exact_tristrokes[layout_.name] = result
        return result

    # May cache this eventually but it's probably not worth
    def amalgamated_bistroke_medians(self, layout_: Layout):
        """Note that the returned dict is a defaultdict."""
        bi_medians: dict[Nstroke, float] = defaultdict(list)
        for tristroke in self.exact_tristrokes_for_layout(layout_):
            bi0 = (
                Nstroke(
                    tristroke.note, tristroke.fingers[:2],
                    tristroke.coords[:2]
                ),
                self.tri_medians[tristroke][0]
            )
            bi1 = (
                Nstroke(
                    tristroke.note, tristroke.fingers[1:], 
                    tristroke.coords[1:]
                ),
                self.tri_medians[tristroke][1]
            )
            for bi_tuple in (bi0, bi1):
                bi_medians[bi_tuple[0]].append(bi_tuple[1])
        for bistroke in bi_medians:
            bi_medians[bistroke] = statistics.fmean(bi_medians[bistroke])

        return bi_medians
        
    def bistroke_category_data(self, layout_: Layout):
        """Returns a 
        dict[category: string, (speed: float, num_samples: int)]
        where num_samples is the number of unique bistroke median speeds that 
        have been averaged to obtain the speed stat. num_samples is positive 
        if speed is obtained from known data, and negative if speed is 
        estimated from related data, which occurs if no known data is 
        directly applicable.
        """
        existing = _find_existing_cached(self.bicatdata, layout_)
        if existing is not None:
            return existing

        known_medians: dict[str, list[float]]
        known_medians = defaultdict(list) # cat -> [speeds]
        total = [] # list[median]
        for tristroke in self.exact_tristrokes_for_layout(layout_):
            for indices in ((0, 1), (1, 2)):
                data = self.tri_medians[tristroke][indices[0]]
                total.append(data)
                category = nstroke.bistroke_category(tristroke, *indices)
                known_medians[category].append(data)
        
        # now estimate missing data
        all_medians: dict[str, list[float]] = {} # cat -> [speeds]
        is_estimate: dict[str, bool] = {} # cat -> bool
        
        all_categories = nstroke.all_bistroke_categories.copy()

        for category in all_categories: # sorted general -> specific
            if category in known_medians:
                all_medians[category] = known_medians[category]
                is_estimate[category] = False
            else:
                is_estimate[category] = True
                if not category:
                    is_estimate[category] = total
                all_medians[category] = []
                for subcategory in known_medians:
                    if subcategory.startswith(category):
                        all_medians[category].extend(
                            known_medians[subcategory])
                    # There may be no subcategories with known data either. 
                    # Hence the next stages
        
        # Assuming sfs is the limiting factor in a trigram, this may help fill
        # sfb speeds
        if not all_medians["sfb"]:
            for tristroke in self.exact_tristrokes_for_layout():
                if nstroke.tristroke_category(tristroke).startswith("sfs"):
                    all_medians["sfb"].append(self.tri_medians[tristroke][2])
        
        all_categories.reverse() # most specific first
        for category in all_categories:
            if not all_medians[category]: # data needed
                for supercategory in all_categories: # most specific first
                    if (category.startswith(supercategory) and 
                            bool(all_medians[supercategory])):
                        all_medians[category] = all_medians[supercategory]
                        break
        # If there is still any category with no data at this point, that 
        # means there was literally no data in ANY category. that's just 
        # a bruh moment

        result = {}
        for category in all_medians:
            try:
                mean = statistics.fmean(all_medians[category])
            except statistics.StatisticsError:
                mean = 0.0 # bruh
            result[category] = (
                mean,
                -len(all_medians[category]) if is_estimate[category]
                    else len(all_medians[category])
            )
        self.bicatdata[layout_.name] = result
        return result
    
    def tristroke_category_data(self, layout_: Layout):
        """Returns a 
        dict[category: string, (speed: float, num_samples: int)]
        where num_samples is the number of unique bistroke/tristroke median 
        speeds that have been combined to obtain the speed stat. num_samples 
        is positive if speed is obtained from known data, and negative if 
        speed is estimated from related data, which occurs if no known data 
        is directly applicable."""

        existing = _find_existing_cached(self.tricatdata, layout_)
        if existing is not None:
            return existing

        known_medians: dict[str, list[float]]
        known_medians = defaultdict(list) # cat -> [speeds]
        total = [] # list[speeds]
        for tristroke in self.exact_tristrokes_for_layout(layout_):
            data = self.tri_medians[tristroke][2]
            total.append(data)
            category = nstroke.tristroke_category(tristroke)
            known_medians[category].append(data)
            
        # now estimate missing data
        all_medians: dict[str, list[float]] = {} # cat -> [speeds]
        is_estimate: dict[str, bool] = {} # cat -> bool

        all_categories = nstroke.all_tristroke_categories.copy()

        # Initial transfer
        for category in all_categories: # sorted general -> specific
            is_estimate[category] = False
            if category in known_medians:
                all_medians[category] = known_medians[category]
            else: # fill in from subcategories
                if not category:
                    all_medians[category] = total
                    continue
                all_medians[category] = []
                if category.startswith("."):
                    for instance in known_medians:
                        if instance.endswith(category):
                            all_medians[category].extend(known_medians[instance])
                else:
                    if not category.endswith("."):
                        is_estimate[category] = True
                    for subcategory in known_medians:
                        if subcategory.startswith(category):
                            all_medians[category].extend(known_medians[subcategory])
                # There may be no subcategories with known data either. 
                # Hence the next stages
        
        # Fill from other categories
        if not all_medians["sfb."]:
            for tristroke in self.tri_medians:
                if nstroke.tristroke_category(tristroke).startswith("sfr"):
                    all_medians["sfb."].append(self.tri_medians[tristroke][2])
        
        all_categories.reverse() # most specific first

        # fill in from supercategory
        for category in all_categories:
            if not all_medians[category] and not category.startswith("."):
                for supercategory in all_categories:
                    if (category.startswith(supercategory) and 
                            bool(all_medians[supercategory]) and
                            category != supercategory):
                        all_medians[category] = all_medians[supercategory]
                        break
        # fill in scissors from subcategories
        for category in all_categories:
            if not all_medians[category] and category.startswith("."):
                is_estimate[category] = True # the subcategory is an estimate
                for instance in all_categories:
                    if (instance.endswith(category) and instance != category):
                        all_medians[category].extend(all_medians[instance])
        # If there is still any category with no data at this point, that means
        # there was literally no data in ANY category. that's just a bruh moment

        result = {}
        for category in all_medians:
            try:
                mean = statistics.fmean(all_medians[category])
            except statistics.StatisticsError:
                mean = 0.0 # bruh
            result[category] = (
                mean,
                -len(all_medians[category]) if is_estimate[category]
                    else len(all_medians[category])
            )

        self.tricatdata[layout_.name] = result
        return result

    def tristroke_breakdowns(self, layout_: Layout):
        """Returns a result such that result[category][bistroke] gives
        (speed, num_samples) for bistrokes obtained by breaking down tristrokes
        in that category. 

        This data is useful to estimate the speed of an unknown tristroke by 
        piecing together its component bistrokes, since those may be known.
        """
        existing = _find_existing_cached(self.tribreakdowns, layout_)
        if existing is not None:
            return existing

        samples: dict[str, dict[Nstroke, list[float]]]
        samples = {cat: defaultdict(list) for cat in nstroke.all_tristroke_categories}
        for ts in self.exact_tristrokes_for_layout(layout_): # ts is tristroke
            cat = nstroke.tristroke_category(ts)
            bistrokes = (
                Nstroke(ts.note, ts.fingers[:2], ts.coords[:2]),
                Nstroke(ts.note, ts.fingers[1:], ts.coords[1:])
            )
            for i, b in enumerate(bistrokes):
                speed = self.tri_medians[ts][i]
                samples[cat][b].append(speed)
        result: dict[str, dict[str, tuple(float, int)]] 
        result = {cat: dict() for cat in samples}
        for cat in samples:
            for bs in samples[cat]: # bs is bistroke
                mean = statistics.fmean(samples[cat][bs])
                count = len(samples[cat][bs])
                result[cat][bs] = (mean, count)
        return result

    def tristroke_speed_calculator(self, layout_: Layout):
        """Returns a function speed(ts) which determines the speed of the 
        tristroke ts. Uses data from medians if it exists; if not, uses 
        tribreakdowns as a fallback, and if that still fails then
        uses the average speed of the category from tricatdata.
        Caching is used for additional speed.
        
        The function returns (duration in ms, is_exact)"""

        existing = _find_existing_cached(self.speed_funcs, layout_)
        if existing is not None:
            return existing

        tribreakdowns = self.tristroke_breakdowns(layout_)
        tricatdata = self.tristroke_category_data(layout_)
        
        @functools.cache
        def speed_func(ts: Tristroke):
            cat = nstroke.tristroke_category(ts)
            try:
                speed = self.tri_medians[ts][2]
                is_exact = True
            except KeyError: # Use breakdown data instead
                is_exact = False
                try:
                    speed = 0.0
                    bs1 = Nstroke(ts.note, ts.fingers[:2], ts.coords[:2])
                    speed += tribreakdowns[cat][bs1][0]
                    bs2 = Nstroke(ts.note, ts.fingers[1:], ts.coords[1:])
                    speed += tribreakdowns[cat][bs2][0]
                except KeyError: # Use general category speed
                    speed = tricatdata[cat][0]
            return (speed, is_exact)

        return speed_func

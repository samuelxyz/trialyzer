import csv
import statistics
from collections import defaultdict
from typing import Dict, List, Tuple
import itertools
import operator

from board import Coord
from fingermap import Finger
import nstroke

# Planned as a way to consolidate medians, bistroke/tristroke speed data, etc
# Goals:
#   - Cache all tristroke medians/other data in one place
#       - Compute new ones when needed
#   - Update when csvdata is updated
#       - dedicated add/remove functions clear affected data from caches
#       - to switch csvfiles, just wipe everything
#       - should the filename be a field then? yeah ig
#   - 

Tristroke = nstroke.Tristroke

class TypingData:
    def __init__(self, csv_filename: str) -> None:
        """Raises OSError if data/csv_filename.csv not found."""
        self.csv_filename = csv_filename
        self.load_csv()

        # dict(Tristroke: [speeds_01], [speeds_12])
        self.csv_data: Dict[Tristroke, Tuple[List, List]]
        self.csv_data = defaultdict(lambda: ([], []))

        # dict(Tristroke: speed_01, speed_12, speed_02)
        self.medians: Dict[Tristroke, Tuple[float, float, float]] 
        self.medians = {}
    
    def load_csv(self):
        with open("data/" + self.csv_filename + ".csv", 
                "r", newline="") as csvfile:
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
    
    def save_csv(self, filename: str):
        header = [
            "note", "finger0", "finger1", "finger2",
            "x0", "y0", "x1", "y1", "x2", "y2"
        ]
        with open("data/" + filename + ".csv", "w", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(header)
            for tristroke in self.csv_data:
                if not self.csv_data[tristroke] or not self.csv_data[tristroke][0]:
                    continue
                row = self._start_csv_row(tristroke)
                row.extend(itertools.chain.from_iterable(
                    zip(self.csv_data[tristroke][0], 
                        self.csv_data[tristroke][1])))
                w.writerow(row)
    
    def _start_csv_row(tristroke: Tristroke):
        """Order of returned data: note, fingers, coords"""
        
        result = [tristroke.note]
        result.extend(f.name for f in tristroke.fingers)
        result.extend(itertools.chain.from_iterable(tristroke.coords))
        return result

    def get_tristroke_medians(self, tristroke: Tristroke):
        """Returns (speed_01, speed_12, speed_02) if relevant csv data exists,
        otherwise returns None.
        """
        if tristroke in self.medians:
            return self.medians[tristroke]

        speeds_01: List[float] = []
        speeds_12: List[float] = []
        for csv_tristroke in self.csv_data:
            if csv_tristroke.fingers == tristroke.fingers:
                if nstroke.compatible(tristroke, csv_tristroke):
                    speeds_01.extend(self.csv_data[csv_tristroke][0])
                    speeds_12.extend(self.csv_data[csv_tristroke][1])
        speeds_02: List[float] = map(operator.add, speeds_01, speeds_12)
        try:
            data = (
                statistics.median(speeds_01),
                statistics.median(speeds_12),
                statistics.median(speeds_02)
            )
            self.medians[tristroke] = data
            return data
        except statistics.StatisticsError:
            return None
    
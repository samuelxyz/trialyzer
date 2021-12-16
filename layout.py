import board
import fingermap

class Layout:

    loaded = {} # dict of layouts

    def __init__(self, name: str) -> None:
        self.name = name
        self.keys = {} # dict Pos -> keyname
        self.positions = {} # dict keyname -> Pos
        self.fingermap = None
        self.board = None
        with open("layouts/" + name) as file:
            self.build_from_string(file.read())

    def build_from_string(self, s: str):
        rows = []
        first_row = fingermap.Row.TOP
        first_col = 1
        for row in s.split("\n"):
            tokens = row.split(" ")
            if tokens[0] == "fingermap:" and len(tokens) >= 2:
                self.fingermap = fingermap.get_fingermap(tokens[1])
            elif tokens[0] == "board:" and len(tokens) >= 2:
                self.board = board.get_board(tokens[1])
            elif tokens[0] == "first_pos:" and len(tokens) >= 3:
                try:
                    first_row = int(tokens[1])
                except ValueError:
                    first_row = fingermap.Row[tokens[1]]
                first_col = int(tokens[2])
            else:
                rows.append(tokens)
        for r, row in enumerate(rows):
            for c, key in enumerate(row):
                if key:
                    pos = fingermap.Pos(first_row + r, first_col + c)
                    self.keys[pos] = key
                    self.positions[key] = pos

    def __str__(self) -> str:
        return (self.name + " (" + self.fingermap.name + ", " 
            + self.board.name +  ")")

def get_layout(name: str) -> Layout:
    try:
        return Layout.loaded[name]
    except KeyError:
        Layout.loaded[name] = Layout(name)
        return Layout.loaded[name]
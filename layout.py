import fingermap

class Layout:
    name = ""
    keys = {}
    positions = {}
    fingermap = ""

    def __init__(self, name) -> None:
        self.name = name
        with open("layouts/" + name) as file:
            self.build_from_string(file.read())

    def build_from_string(self, s):
        rows = []
        first_row = fingermap.Row.TOP
        first_col = 1
        for row in s.split("\n"):
            tokens = row.split(" ")
            if tokens[0] == "fingermap:" and len(tokens) >= 2:
                self.fingermap = tokens[1]
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
        
    def get_key(self, pos):

        return self.keys[pos]

    def get_position(self, key):

        return self.positions[key]

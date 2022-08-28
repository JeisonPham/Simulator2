class DuplicateNameException(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Name already exists in rendering window: {name}")


class NullMeshObjectException(Exception):
    def __init__(self):
        super().__init__("There was no mesh file foudn")

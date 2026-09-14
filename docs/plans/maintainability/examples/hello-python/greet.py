"""Two greeters that share a name, so name resolution and type resolution differ."""


def greet(name: str) -> str:
    """Greet at module level."""
    return f"Hello, {name}!"


class Greeter:
    """A greeter that carries its own prefix."""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def greet(self, name: str) -> str:
        """Greet as a method, sharing a name with the module-level function."""
        return f"{self.prefix}, {name}!"

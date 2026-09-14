"""One callee with two call sites, and one call only a type can resolve."""

from greet import Greeter, greet


def main() -> None:
    """Call the module-level greet twice, then the method of the same name once."""
    print(greet("world"))
    print(greet("again"))
    print(Greeter("Howdy").greet("world"))


if __name__ == "__main__":
    main()

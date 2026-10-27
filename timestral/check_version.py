"""Fail an image build when its installed upstream Timestral version differs."""

import importlib.metadata
import sys


def main() -> int:
    expected = sys.argv[1]
    try:
        actual = importlib.metadata.version("timestral")
    except importlib.metadata.PackageNotFoundError:
        print("Timestral distribution is not installed", file=sys.stderr)
        return 1

    if actual != expected:
        print(
            f"Timestral package version {actual} does not match image version {expected}",
            file=sys.stderr,
        )
        return 1

    print(f"Verified Timestral package version {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

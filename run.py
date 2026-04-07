"""
Mayo Data Pipeline — main entry point.
Runs the full pipeline: collect → score → output.
"""

from dotenv import load_dotenv

load_dotenv()


def main():
    print("Mayo Data Pipeline")
    print("------------------")
    # TODO: wire up connectors, scoring, and output


if __name__ == "__main__":
    main()

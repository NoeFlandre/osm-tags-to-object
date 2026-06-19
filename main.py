"""Console entrypoint shim. The real CLI lives in :mod:`osm_tags_to_object.cli`."""

from osm_tags_to_object.cli import cli

if __name__ == "__main__":
    cli()

import argparse
import sys

from . import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aprx",
        description="Version-control tooling for ArcGIS .aprx project files.",
    )
    parser.add_argument("--version", action="version", version=f"aprx-tools {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # explode
    p = sub.add_parser("explode", help="Extract an .aprx into a diffable directory.")
    p.add_argument("aprx_file", metavar="file.aprx")
    p.add_argument("output_dir", metavar="output_dir", nargs="?",
                   help="Destination directory (default: <file>.aprx.src)")

    # pack
    p = sub.add_parser("pack", help="Pack a directory back into an .aprx file.")
    p.add_argument("src_dir", metavar="dir")
    p.add_argument("output_file", metavar="output.aprx", nargs="?",
                   help="Destination file (default: derived from directory name)")

    # compare
    p = sub.add_parser("compare", help="Semantically diff two .aprx files or directories.")
    p.add_argument("a", metavar="a")
    p.add_argument("b", metavar="b")

    # install
    sub.add_parser("install", help="Install git hooks into the current repository.")

    # hook (internal — called by the installed hook scripts)
    p = sub.add_parser("hook", help=argparse.SUPPRESS)
    p.add_argument("hook_name", choices=["pre-commit", "post-stash"])

    args = parser.parse_args()

    if args.command == "explode":
        from .explode import explode
        explode(args.aprx_file, args.output_dir)

    elif args.command == "pack":
        from .pack import pack
        pack(args.src_dir, args.output_file)

    elif args.command == "compare":
        from .compare import compare
        has_diff = compare(args.a, args.b)
        if not has_diff:
            print("Identical: all files match semantically.")
        sys.exit(1 if has_diff else 0)

    elif args.command == "install":
        from .install import install_hooks
        install_hooks()

    elif args.command == "hook":
        from .hooks import hook_pre_commit, hook_post_stash
        if args.hook_name == "pre-commit":
            hook_pre_commit()
        else:
            hook_post_stash()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

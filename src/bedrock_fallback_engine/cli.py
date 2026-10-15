"""
CLI for bedrock-fallback-engine.

Currently ships one command: ``package`` — builds a Lambda-ready zip of
this library plus its dependencies.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

logger = logging.getLogger("bedrock_fallback_engine.cli")

DEFAULT_OUTPUT = Path("dist/lambda_layer.zip")


def _build_package(output: Path, include_boto3: bool) -> int:
    """
    Build a Lambda deployment zip.

    Args:
        output: Path to the resulting .zip file.
        include_boto3: Whether to bundle boto3 in the zip. Lambda's runtime
            already includes boto3, so this defaults to False to keep the
            zip small. Set True for a self-contained zip.

    Returns:
        Shell exit code (0 = success).
    """
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        output.unlink()

    with tempfile.TemporaryDirectory() as tmpdir:
        staging = Path(tmpdir) / "build"
        staging.mkdir()

        # 1. Install the package (and deps) into the staging folder.
        install_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            ".",
            "--target",
            str(staging),
            "--quiet",
            "--upgrade",
        ]
        if not include_boto3:
            # boto3 is provided by the Lambda runtime; skip it.
            install_cmd.extend(["--no-deps"])
            install_cmd.extend(["--quiet"])

        logger.info("Installing package into staging dir: %s", staging)
        result = subprocess.run(install_cmd, check=False)
        if result.returncode != 0:
            logger.error("pip install failed with code %d", result.returncode)
            return result.returncode

        # If we skipped deps, we need to install pydantic manually.
        if not include_boto3:
            pydantic_cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "pydantic>=2.0",
                "--target",
                str(staging),
                "--quiet",
                "--upgrade",
            ]
            result = subprocess.run(pydantic_cmd, check=False)
            if result.returncode != 0:
                logger.error("pydantic install failed with code %d", result.returncode)
                return result.returncode

        # 2. Zip everything up.
        logger.info("Zipping %s -> %s", staging, output)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in staging.rglob("*"):
                if file.is_file():
                    zipf.write(file, file.relative_to(staging))

    size_mb = output.stat().st_size / (1024 * 1024)
    logger.info("Done. Wrote %s (%.2f MB)", output, size_mb)
    print(f"✅ Wrote {output}")
    print(f"   Size: {size_mb:.2f} MB")
    print()
    print("Deploy with:")
    print(
        f"   aws lambda update-function-code "
        f"--function-name <YOUR_FUNCTION> --zip-file fileb://{output}"
    )
    return 0


def _cmd_package(args: argparse.Namespace) -> int:
    return _build_package(
        output=Path(args.output),
        include_boto3=args.include_boto3,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bedrock-fallback-engine",
        description="Tools for building and deploying Bedrock fallback applications.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pkg = subparsers.add_parser(
        "package",
        help="Build a Lambda-ready deployment zip of bedrock-fallback-engine.",
    )
    pkg.add_argument(
        "--output",
        "-o",
        default=str(DEFAULT_OUTPUT),
        help=f"Output .zip path (default: {DEFAULT_OUTPUT}).",
    )
    pkg.add_argument(
        "--include-boto3",
        action="store_true",
        help="Bundle boto3 in the zip (Lambda's runtime already provides it).",
    )
    pkg.set_defaults(func=_cmd_package)

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

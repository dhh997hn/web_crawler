from __future__ import annotations

import argparse
import logging
import os
import sys

from .config import load_config, load_credentials
from .crawler import Crawler


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="web-crawler",
        description="Crawl data from an API/HTML website with login credentials",
    )
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to config file")
    parser.add_argument(
        "-k", "--credentials", default="credentials.yaml",
        help="Path to credentials file (or use CRAWLER_USERNAME/CRAWLER_PASSWORD env vars)",
    )
    parser.add_argument("--no-resume", action="store_true", help="Ignore checkpoint, crawl from scratch")
    parser.add_argument("--max-pages", type=int, default=0, help="Override max pages to crawl")
    parser.add_argument("--output", help="Override output file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    log = logging.getLogger("crawler")
    if not os.path.exists(args.config):
        log.error(
            "Config file not found: %s. Dung -c de chi dinh (vd: -c config.voz.yaml) "
            "hoặc copy: cp config.voz.yaml %s",
            args.config, args.config,
        )
        return 1
    try:
        config = load_config(args.config)
        creds = load_credentials(args.credentials)
        if args.output:
            config.output.file = args.output
        crawler = Crawler(config, creds)
        summary = crawler.run(resume=not args.no_resume, max_pages=args.max_pages)
        log.info("Done: %s", summary)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        log.error("Crawl failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

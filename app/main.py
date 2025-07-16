import argparse
from crawler import InstaCrawler

def main():
    parser = argparse.ArgumentParser(description="Instagram Hashtag Crawler")
    parser.add_argument("--tags", nargs="+", required=True, help="해시태그 입력 (예: --tags 서울맛집 카페투어)")
    args = parser.parse_args()

    crawler = InstaCrawler()
    crawler.run(args.tags)

if __name__ == "__main__":
    main()
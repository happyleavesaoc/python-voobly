import argparse
import json
import os
import re

from voobly import get_session, make_scrape_request


DATA_PATH = 'metadata'
LADDER_ID_REGEX = '^/profile/view/'
LADDER_URL_REGEX = '^https://voobly.com/ladder/view'


def get_ladder_metadata(session, url):
    """Get ladder metadata."""
    parsed = make_scrape_request(session, url)
    tag = parsed.find('a', href=re.compile(LADDER_ID_REGEX))
    return {
        'id': int(tag['href'].split('/')[-1]),
        'slug': url.split('/')[-1],
        'url': url
    }


def get_ladders_metadata(session, parsed):
    """Get metadata for all ladders."""
    ladders = {}
    for ladder in parsed.find_all('a', href=re.compile(LADDER_URL_REGEX)):
        ladders[ladder.text] = get_ladder_metadata(session, ladder['href'])
    return ladders


def get_metadata(session, games):
    """Get metadata for games (only ladder data right now)."""
    for data in games.values():
        parsed = make_scrape_request(session, data['url'])
    return {
        'ladders': get_ladders_metadata(session, parsed)
    }


def update_metadata(session, path=DATA_PATH):
    """Update metadata files (only ladders right now)."""
    with open(os.path.join(path, 'games.json')) as handle:
        games = json.loads(handle.read())
     
    for key, data in get_metadata(session, games).items():
        with open(os.path.join(path, '{}.json'.format(key)), 'w') as handle:
           handle.write(json.dumps(data, indent=2))


if __name__ == '__main__':
    """Entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username', required=True)
    parser.add_argument('-p', '--password', required=True)
    args = parser.parse_args()
    session = get_session(None, args.username, args.password, cache=False)
    update_metadata(session)

"""Voobly API.

Documentation: http://www.voobly.com/pages/view/147/External-API-Documentation

A Voobly user account is required.
An API key granted by Voobly is also requred.

Please note that every attempt has been made to avoid scraping, to include:
    - caching reference metadata
    - caching requests
    - limiting scraping to essential functionality
    - fully supporting external API
"""

import datetime
import io
import json
import logging
import os
import pkg_resources
import pickle
import re
import zipfile

import bs4
import dateparser
import requests
import requests_cache
import tablib
from requests.auth import AuthBase
from requests.exceptions import RequestException
from tablib.core import UnsupportedFormat


_LOGGER = logging.getLogger(__name__)
COOKIE_PATH = './voobly_cookies.pickle'
BASE_URL_GLOBAL = 'https://www.voobly.com'
BASE_URL_CN = 'http://www.vooblycn.com'
VERSION_GLOBAL = 'voobly'
VERSION_CN = 'vooblycn'
BASE_URLS = {
    VERSION_GLOBAL: BASE_URL_GLOBAL,
    VERSION_CN: BASE_URL_CN
}
VOOBLY_API_URL = '/api/'
LOGIN_PAGE = '/login'
LOGIN_URL = '/login/auth'
MATCH_URL = '/match/view'
TEAM_MATCHES_URL = 'teammatches/index/games/matches/team'
LADDER_MATCHES_URL = '/ladder/matches'
LADDER_RANKING_URL = '/ladder/ranking'
PROFILE_URL = '/profile/view'
PROFILE_PATH = '/profile/view'
FIND_USER_URL = 'finduser/'
FIND_USERS_URL = 'findusers/'
LOBBY_URL = 'lobbies/'
LADDER_URL = 'ladder/'
USER_URL = 'user/'
FRIENDS_URL = '/friends'
USER_SEARCH_URL = FRIENDS_URL + '/browse/Search/Search'
VALIDATE_URL = 'validate'
LADDER_RESULT_LIMIT = 40
METADATA_PATH = 'metadata'
SCRAPE_FETCH_ERROR = 'Page Access Failed'
SCRAPE_PAGE_NOT_FOUND = 'Page Not Found'
MATCH_NEW_RATE = 'New Rating:'
MATCH_DATE_PLAYED = 'Date Played:'
MAX_MATCH_PAGE_ID = 100
MAX_LADDER_PAGE_ID = 100
MAX_RANK_PAGE_ID = 100
LADDER_MATCH_LIMIT = 1000
GAME_AOC = 'Age of Empires II: The Conquerors'
COLOR_MAPPING = {
    '#0054A6': 0,
    '#FF0000': 1,
    '#00A651': 2,
    '#FFFF00': 3,
    '#00FFFF': 4,
    '#92278F': 5,
    '#C0C0C0': 6,
    '#FF8000': 7
}


def get_metadata_path(name):
    """Get reference metadata file path."""
    return pkg_resources.resource_filename('voobly', os.path.join(METADATA_PATH, '{}.json'.format(name)))


GAMES = json.loads(open(get_metadata_path('games')).read())
LADDERS = json.loads(open(get_metadata_path('ladders')).read())


class VooblyError(Exception):
    """Voobly error."""

    pass


def _save_cookies(requests_cookiejar, filename):
    """Save cookies to a file."""
    with open(filename, 'wb') as handle:
        pickle.dump(requests_cookiejar, handle)


def _load_cookies(filename):
    """Load cookies from a file."""
    with open(filename, 'rb') as handle:
        return pickle.load(handle)


def _make_request(session, url, argument=None, params=None, raw=False):
    """Make a request to API endpoint."""
    if not params:
        params = {}
    params['key'] = session.auth.key
    try:
        if argument:
            request_url = '{}{}{}{}'.format(session.auth.base_url, VOOBLY_API_URL, url, argument)
        else:
            request_url = '{}{}'.format(VOOBLY_API_URL, url)
        resp = session.get(request_url, params=params)
    except RequestException:
        raise VooblyError('failed to connect')
    if resp.text == 'bad-key':
        raise VooblyError('bad api key')
    elif resp.text == 'too-busy':
        raise VooblyError('service too busy')
    elif not resp.text:
        raise VooblyError('no data returned')
    if raw:
        return resp.text
    try:
        return tablib.Dataset().load(resp.text).dict
    except UnsupportedFormat:
        raise VooblyError('unexpected error {}'.format(resp.text))


def make_scrape_request(session, url, mode='get', data=None):
    """Make a request to URL."""
    try:
        html = session.request(mode, url, data=data)
    except RequestException:
        raise VooblyError('failed to connect')
    if SCRAPE_FETCH_ERROR in html.text:
        raise VooblyError('not logged in')
    if html.status_code != 200 or SCRAPE_PAGE_NOT_FOUND in html.text:
        raise VooblyError('page not found')
    return bs4.BeautifulSoup(html.text, features='html.parser')


def lookup_ladder_id(name):
    """Lookup ladder id based on name."""
    if name not in LADDERS:
        raise ValueError('could not find ladder id for "{}"'.format(name))
    return LADDERS[name]['id']


def lookup_game_id(name):
    """Lookup game id based on name."""
    if name not in GAMES:
        raise ValueError('could not find game id for "{}"'.format(name))
    return GAMES[name]['id']


# pylint: disable=too-many-arguments
def get_ladder(session, ladder_id, user_id=None, user_ids=None, start=0, limit=LADDER_RESULT_LIMIT):
    """Get ladder."""
    params = {
        'start': start,
        'limit': limit
    }
    if isinstance(ladder_id, str):
        ladder_id = lookup_ladder_id(ladder_id)
    if limit > LADDER_RESULT_LIMIT:
        raise VooblyError('limited to 40 rows')
    if user_ids:
        params['uidlist'] = ','.join([str(uid) for uid in user_ids])
    elif user_id:
        params['uid'] = user_id
    resp = _make_request(session, LADDER_URL, ladder_id, params)
    if user_id:
        if not resp:
            raise VooblyError('user not ranked')
        return resp[0]
    return resp


def get_lobbies(session, game_id):
    """Get lobbies for a game."""
    if isinstance(game_id, str):
        game_id = lookup_game_id(game_id)
    lobbies = _make_request(session, LOBBY_URL, game_id)
    for lobby in lobbies:
        # pylint: disable=len-as-condition
        if len(lobby['ladders']) > 0:
            lobby['ladders'] = lobby['ladders'][:-1].split('|')
    return lobbies


def get_user(session, user_id):
    """Get user."""
    try:
        user_id = int(user_id)
    except ValueError:
        user_id = find_user(session, user_id)
    resp = _make_request(session, USER_URL, user_id)
    if not resp:
        raise VooblyError('user id not found')
    return resp[0]


def find_user(session, username):
    """Find user by name - returns user ID."""
    resp = _make_request(session, FIND_USER_URL, username)
    if not resp:
        raise VooblyError('user not found')
    try:
        return int(resp[0]['uid'])
    except ValueError:
        raise VooblyError('user not found')


def find_users(session, *usernames):
    """Find multiple users by name."""
    user_string = ','.join(usernames)
    return _make_request(session, FIND_USERS_URL, user_string)


def validate_key(session):
    """Validate API key."""
    resp = _make_request(session, VALIDATE_URL, raw=True)
    return resp == 'valid-key'


def user(session, uid, ladder_ids=None):
    """Get all possible user info by name."""
    data = get_user(session, uid)
    resp = dict(data)
    if not ladder_ids:
        return resp
    resp['ladders'] = {}
    for ladder_id in ladder_ids:
        if isinstance(ladder_id, str):
            ladder_id = lookup_ladder_id(ladder_id)
        try:
            ladder_data = dict(get_ladder(session, ladder_id, user_id=uid))
            resp['ladders'][ladder_id] = ladder_data
        except VooblyError:
            # No ranking on ladder
            pass
    return resp


def ladders(session, game_id):
    """Get a list of ladder IDs."""
    if isinstance(game_id, str):
        game_id = lookup_game_id(game_id)
    lobbies = get_lobbies(session, game_id)
    ladder_ids = set()
    for lobby in lobbies:
        ladder_ids |= set(lobby['ladders'])
    return list(ladder_ids)


def authenticated(function):
    """Re-authenticate if session expired."""
    def wrapped(session, *args, **kwargs):
        """Wrap function."""
        try:
            return function(session, *args, **kwargs)
        except VooblyError:
            with session.cache_disabled():
                _LOGGER.info("attempted to access page before login")
                login(session)
                return function(session, *args, **kwargs)
    return wrapped


@authenticated
def find_user_anon(session, username):
    parsed = make_scrape_request(session, session.auth.base_url + FRIENDS_URL)
    sid = parsed.find('input', {'name': 'session1'})['value']
    resp = session.post(session.auth.base_url + USER_SEARCH_URL, data={'query': username, 'session1': sid}, allow_redirects=False)
    if resp.status_code == 200:
        raise VooblyError('user not found')
    try:
        return int(resp.headers['Location'].split('/')[-1])
    except ValueError:
        raise VooblyError('user not found')


@authenticated
def user_anon(session, user_id, ladder_ids=None):
    try:
        user_id = int(user_id)
    except ValueError:
        user_id = find_user_anon(session, user_id)
    parsed = make_scrape_request(session, '{}{}/{}/Ratings'.format(session.auth.base_url, PROFILE_URL, user_id))
    username = parsed.find('title').text
    img = parsed.find('img', {'width': '200'})
    nation_id = parsed.find(text='Country:').find_next('div').find('img')['src'].split('/')[-1].replace('.png', '')
    tid = None
    team = parsed.find('div', {'id': 'profile-team'})
    if team:
        tid = int(team.find('div', {'class': 'picture'}).find('a')['href'].split('/')[-1])
    ladders = {}
    for row in parsed.find(text='Ladder Statistics').find_next('table').find_all('tr')[1:]:
        cols = row.find_all('td')
        try:
            name = cols[2].find('a').text
            if name not in ladder_ids:
                continue
            ladders[lookup_ladder_id(name)] = {
                'uid': user_id,
                'rank': 1,
                'rating': int(cols[3].text),
                'wins': int(cols[4].text),
                'losses': int(cols[5].text),
                'streak': int(cols[6].find('font').text)
            }
        except ValueError:
            pass
    return {
        'uid': user_id,
        'display_name': username,
        'name': img['alt'],
        'imagelarge': img['src'] if img['src'].startswith('http') else '{}{}'.format(session.auth.base_url, img['src']),
        'imagesmall': None,
        'last_login': 0,
        'account_created': 0,
        'tid': tid,
        'nationid': nation_id,
        'ladders': ladders
    }


@authenticated
def get_ladder_anon(session, ladder_id, start=0, limit=LADDER_RESULT_LIMIT):
    page_id = 0
    ranks = []
    done = False
    while not done and page_id < MAX_RANK_PAGE_ID:
        url = '{}{}/{}/{}'.format(session.auth.base_url, LADDER_RANKING_URL, lookup_ladder_id(ladder_id), page_id)
        parsed = make_scrape_request(session, url)
        for row in parsed.find(text='Ladder Players').find_next('table').find_all('tr')[1:]:
            cols = row.find_all('td')
            rank = int(cols[0].text)
            if rank < start:
                continue
            elif rank > start + limit:
                done = True
                break
            ranks.append({
                'rank': rank,
                'uid': int(cols[1].find_all('a')[-1]['href'].split('/')[-1]),
                'display_name': ''.join(cols[1].find_all(text=True)).strip(),
                'rating': int(cols[2].text),
                'wins': int(cols[3].text),
                'losses': int(cols[4].text),
                'streak': int(cols[5].find('font').text)
            })
        page_id += 1
    return ranks


@authenticated
def get_clan_matches(session, subdomain, clan_id, from_timestamp=None, limit=None):
    """Get recent matches by clan."""
    return get_recent_matches(session, 'https://{}.voobly.com/{}/{}/0'.format(
        subdomain, TEAM_MATCHES_URL, clan_id), from_timestamp, limit)


@authenticated
def get_user_matches(session, user_id, from_timestamp=None, limit=None):
    """Get recent matches by user."""
    return get_recent_matches(session, '{}{}/{}/Matches/games/matches/user/{}/0'.format(
        session.auth.base_url, PROFILE_URL, user_id, user_id), from_timestamp, limit)


def get_recent_matches(session, init_url, from_timestamp, limit):
    """Get recently played user matches."""
    if not from_timestamp:
        from_timestamp = datetime.datetime.now() - datetime.timedelta(days=1)
    matches = []
    page_id = 0
    done = False
    while not done and page_id < MAX_MATCH_PAGE_ID:
        url = '{}/{}'.format(init_url, page_id)
        parsed = make_scrape_request(session, url)
        for row in parsed.find('table').find_all('tr')[1:]:
            cols = row.find_all('td')
            played_at = dateparser.parse(cols[2].text)
            match_id = int(cols[5].find('a').text[1:])
            has_rec = cols[6].find('a').find('img')
            if played_at < from_timestamp or (limit and len(matches) == limit):
                done = True
                break
            if not has_rec:
                continue
            matches.append({
                'timestamp': played_at,
                'match_id': match_id
            })
        if not matches:
            break
        page_id += 1
    return matches


@authenticated
def get_ladder_matches(session, ladder_id, from_timestamp=None, limit=LADDER_MATCH_LIMIT):
    """Get recently played ladder matches."""
    if not from_timestamp:
        from_timestamp = datetime.datetime.now() - datetime.timedelta(days=1)
    matches = []
    page_id = 0
    done = False
    i = 0
    while not done and page_id < MAX_LADDER_PAGE_ID:
        url = '{}{}/{}/{}'.format(session.auth.base_url, LADDER_MATCHES_URL, lookup_ladder_id(ladder_id), page_id)
        parsed = make_scrape_request(session, url)
        for row in parsed.find(text='Recent Matches').find_next('table').find_all('tr')[1:]:
            cols = row.find_all('td')
            played_at = dateparser.parse(cols[0].text)
            match_id = int(cols[1].find('a').text[1:])
            has_rec = cols[4].find('a').find('img')
            if not has_rec:
                continue
            if played_at < from_timestamp or i >= limit:
                done = True
                break
            matches.append({
                'timestamp': played_at,
                'match_id': match_id
            })
            i += 1
        page_id += 1
    return matches


@authenticated
def get_match(session, match_id):
    """Get match metadata."""
    url = '{}{}/{}'.format(session.auth.base_url, MATCH_URL, match_id)
    parsed = make_scrape_request(session, url)
    game = parsed.find('h3').text
    if game != GAME_AOC:
        raise ValueError('not an aoc match')
    date_played = parsed.find(text=MATCH_DATE_PLAYED).find_next('td').text
    players = []
    colors = {}
    player_count = int(parsed.find('td', text='Players:').find_next('td').text)
    for div in parsed.find_all('div', style=True):
        if not div['style'].startswith('background-color:'):
            continue
        if len(players) == player_count:
            break
        username_elem = div.find_next('a', href=re.compile(PROFILE_PATH))
        username = username_elem.text
        color = div['style'].split(':')[1].split(';')[0].strip()
        colors[username] = color

        rec = None
        for dl_elem in parsed.find_all('a', href=re.compile('^/files/view')):
            rec_name = dl_elem.find('b', text=re.compile(username+'$'))
            if rec_name:
                rec = rec_name.parent

        user = parsed.find('a', text=username)
        if not user:
            # bugged match page
            continue
        user_id = int(user['href'].split('/')[-1])
        span = user.find_next('span')
        if not span:
            continue
        children = list(span.children)
        rate_after = None
        rate_before = None
        if str(children[0]).strip() == MATCH_NEW_RATE:
            rate_after = int(children[1].text)
            rate_before = rate_after - int(children[3].text)
        elif len(children) > 5 and str(children[4]).strip() == MATCH_NEW_RATE:
            rate_after = int(children[5].text)
            rate_before = rate_after - int(children[3].text)
        players.append({
            'url': rec['href'] if rec else None,
            'id': user_id,
            'username': username,
            'color_id': COLOR_MAPPING.get(colors[username]),
            'rate_before': rate_before,
            'rate_after': rate_after
        })
    return {
        'timestamp': dateparser.parse(date_played),
        'players': players
    }


@authenticated
def download_rec(session, rec_url, target_path):
    """Download and extract a recorded game."""
    try:
        resp = session.get(session.auth.base_url + rec_url)
    except RequestException:
        raise VooblyError('failed to connect for download')
    try:
        downloaded = zipfile.ZipFile(io.BytesIO(resp.content))
        downloaded.extractall(target_path)
    except zipfile.BadZipFile:
        raise VooblyError('invalid zip file')
    return downloaded.namelist()[0] # never more than one rec


def login(session):
    """Login to Voobly."""
    if not session.auth.username or not session.auth.password:
        raise VooblyError('must supply username and password')
    _LOGGER.info("logging in (no valid cookie found)")
    session.cookies.clear()
    try:
        session.get(session.auth.base_url + LOGIN_PAGE)
        resp = session.post(session.auth.base_url + LOGIN_URL, data={
            'username': session.auth.username,
            'password': session.auth.password
        })
    except RequestException:
        raise VooblyError('failed to connect for login')
    if resp.status_code != 200:
        raise VooblyError('failed to login')
    _save_cookies(session.cookies, session.auth.cookie_path)


def get_session(key=None, username=None, password=None, cache=True,
                cache_expiry=datetime.timedelta(days=7), cookie_path=COOKIE_PATH, backend='memory',
                version=VERSION_GLOBAL):
    """Get Voobly API session."""
    class VooblyAuth(AuthBase):  # pylint: disable=too-few-public-methods
        """Voobly authorization storage."""

        def __init__(self, key, username, password, cookie_path, version):
            """Init."""
            self.key = key
            self.username = username
            self.password = password
            self.cookie_path = cookie_path
            self.base_url = BASE_URLS[version]

        def __call__(self, r):
            """Call is no-op."""
            return r

    if version not in BASE_URLS:
        raise ValueError('unsupported voobly version')

    session = requests.session()
    if cache:
        session = requests_cache.core.CachedSession(expire_after=cache_expiry, backend=backend)
    session.auth = VooblyAuth(key, username, password, cookie_path, version)
    if os.path.exists(cookie_path):
        _LOGGER.info("cookie found at: %s", cookie_path)
        session.cookies = _load_cookies(cookie_path)
    return session

"""Voobly API.

Documentation: http://www.voobly.com/pages/view/147/External-API-Documentation

A Voobly user account is required.
An API key granted by Voobly is also requred.
"""

import datetime
import logging
import requests
from requests.auth import AuthBase
from requests.exceptions import RequestException
import requests_cache
import tablib


_LOGGER = logging.getLogger(__name__)
VOOBLY_API_URL = 'http://www.voobly.com/api/'
LADDER_URL = 'ladder/'
FIND_USER_URL = 'finduser/'
FIND_USERS_URL = 'findusers/'
LOBBY_URL = 'lobbies/'
USER_URL = 'user/'
VALIDATE_URL = 'validate'
LADDER_RESULT_LIMIT = 40


class VooblyError(Exception):
    """Voobly error."""

    pass


def _make_request(session, url, argument=None, params=None, raw=False):
    """Make a request to API endpoint."""
    if not params:
        params = {}
    params['key'] = session.auth.key
    try:
        if argument:
            request_url = '{}{}{}'.format(VOOBLY_API_URL, url, argument)
        else:
            request_url = '{}{}'.format(VOOBLY_API_URL, url)
        resp = session.get(request_url, params=params)
    except RequestException:
        raise VooblyError('connection problem')
    if resp.text == 'bad-key':
        raise VooblyError('bad api key')
    if not resp.text:
        raise VooblyError('no data returned')
    if raw:
        return resp.text
    return tablib.Dataset().load(resp.text).dict


# pylint: disable=too-many-arguments
def get_ladder(session, ladder_id, user_id=None, user_ids=None, start=0, limit=LADDER_RESULT_LIMIT):
    """Get ladder."""
    params = {
        'start': start,
        'limit': limit
    }
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
    lobbies = _make_request(session, LOBBY_URL, game_id)
    for lobby in lobbies:
        # pylint: disable=len-as-condition
        if len(lobby['ladders']) > 0:
            lobby['ladders'] = lobby['ladders'][:-1].split('|')
    return lobbies


def get_user(session, user_id):
    """Get user."""
    resp = _make_request(session, USER_URL, user_id)
    if not resp:
        raise VooblyError('user id not found')
    return resp[0]


def find_user(session, username):
    """Find user by name - returns user ID."""
    resp = _make_request(session, FIND_USER_URL, username)
    if not resp:
        raise VooblyError('user not found')
    return resp[0]['uid']


def find_users(session, *usernames):
    """Find multiple users by name."""
    user_string = ','.join(usernames)
    return _make_request(session, FIND_USERS_URL, user_string)


def validate_key(session):
    """Validate API key."""
    resp = _make_request(session, VALIDATE_URL, raw=True)
    return resp == 'valid-key'


def user(session, username, ladder_ids=None):
    """Get all possible user info by name."""
    uid = find_user(session, username)
    data = get_user(session, uid)
    resp = dict(data)
    if not ladder_ids:
        return resp
    resp['ladders'] = {}
    for ladder_id in ladder_ids:
        try:
            ladder_data = dict(get_ladder(session, ladder_id, user_id=uid))
            resp['ladders'][ladder_id] = ladder_data
        except VooblyError:
            # No ranking on ladder
            pass
    return resp


def ladders(session, game_id):
    """Get a list of ladder IDs."""
    lobbies = get_lobbies(session, game_id)
    print(lobbies)
    ladder_ids = set()
    for lobby in lobbies:
        ladder_ids |= set(lobby['ladders'])
    return list(ladder_ids)


def get_session(key, cache=True, cache_expiry=datetime.timedelta(days=7)):
    """Get Voobly API session."""
    class VooblyAuth(AuthBase):  # pylint: disable=too-few-public-methods
        """Voobly authorization storage."""

        def __init__(self, key):
            """Init."""
            self.key = key

        def __call__(self, r):
            """Call is no-op."""
            return r

    session = requests.session()
    if cache:
        session = requests_cache.core.CachedSession(expire_after=cache_expiry)
    session.auth = VooblyAuth(key)
    return session

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Service for checking user subscriptions to required channels/chats.
Single place to call Telegram API, handle errors, caching and normalization.
"""
import time
import threading
from telebot.apihelper import ApiTelegramException

# Simple in-memory cache: {(user_id, channel_key): (result_dict, ts)}
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 45  # seconds


def _now_ts():
    return int(time.time())


def _cache_get(user_id, channel_key):
    with _cache_lock:
        entry = _cache.get((user_id, channel_key))
        if not entry:
            return None
        result, ts = entry
        if _now_ts() - ts > CACHE_TTL:
            del _cache[(user_id, channel_key)]
            return None
        return result


def _cache_set(user_id, channel_key, result):
    with _cache_lock:
        _cache[(user_id, channel_key)] = (result, _now_ts())


def clear_cache_for_user(user_id, channels=None):
    """Invalidate subscription cache entries for a user.
    If channels is None, clears all entries for the user. Otherwise clears only for keys in channels.
    """
    with _cache_lock:
        keys_to_delete = []
        if channels is None:
            for (uid, ch_key) in list(_cache.keys()):
                if uid == user_id:
                    keys_to_delete.append((uid, ch_key))
        else:
            ch_set = {str(c) for c in channels}
            for (uid, ch_key) in list(_cache.keys()):
                if uid == user_id and str(ch_key) in ch_set:
                    keys_to_delete.append((uid, ch_key))
        for k in keys_to_delete:
            try:
                del _cache[k]
            except KeyError:
                pass


def normalize_chat_identifier(raw):
    """Normalize stored channel identifier to something Telegram accepts.
    Accepts numeric ids, @usernames, or t.me links.
    Returns either int chat_id or string username WITH leading '@'.
    """
    if raw is None:
        return raw
    s = str(raw).strip()
    # t.me/username or https://t.me/username
    if s.startswith('https://') or s.startswith('http://'):
        if 't.me/' in s:
            uname = s.split('t.me/')[-1].strip('/')
            if uname and not uname.startswith('@') and not uname.lstrip('-').isdigit():
                return f"@{uname}"
            return uname
    if s.startswith('t.me/'):
        uname = s.split('t.me/')[-1].strip('/')
        if uname and not uname.startswith('@') and not uname.lstrip('-').isdigit():
            return f"@{uname}"
        return uname
    # plain @username
    if s.startswith('@'):
        return s
    # numeric id
    if s.lstrip('-').isdigit():
        try:
            nid = int(s)
            return nid
        except Exception:
            return s
    # plain username without @ -> add @
    return f"@{s}"


def map_member_status(member_status):
    """Map Telegram ChatMember.status to our status strings."""
    if member_status in ['member', 'administrator', 'creator']:
        return 'subscribed'
    if member_status in ['left', 'kicked']:
        return 'not_subscribed'
    if member_status == 'restricted':
        # restricted may still have read permissions; treat as not_subscribed (per spec)
        return 'not_subscribed'
    return 'not_subscribed'


def check_user_subscriptions(bot, user_id, channels, logger=None):
    """Check list of channels/chats for user's membership.

    Returns dict: {channel_raw: {'status': 'subscribed'|'not_subscribed'|'unavailable', 'chat_id':..., 'error': ...}}
    """
    results = {}
    for channel in channels or []:
        key = str(channel)
        cached = _cache_get(user_id, key)
        if cached is not None:
            results[key] = cached
            continue

        normalized = normalize_chat_identifier(channel)
        try:
            # Try get_chat_member directly; Telebot accepts username (with '@') or id
            if isinstance(normalized, str):
                chat_id_for_api = normalized if normalized.startswith('@') else f"@{normalized}"
            else:
                chat_id_for_api = normalized
            if logger:
                try:
                    logger(f"[DEBUG] get_chat_member(chat_id={chat_id_for_api}, user_id={user_id})")
                except Exception:
                    pass
            member = bot.get_chat_member(chat_id=chat_id_for_api, user_id=user_id)
            status_mapped = map_member_status(getattr(member, 'status', None))
            # Some ChatMember objects (e.g., ChatMemberMember) do not expose 'chat'. Use normalized id.
            res = {'status': status_mapped, 'chat_id': chat_id_for_api, 'error': None}
            results[key] = res
            _cache_set(user_id, key, res)
        except ApiTelegramException as e:
            msg = str(e).lower()
            # Bot has no access or chat not found
            if 'forbidden' in msg or 'bot was blocked' in msg or 'chat not found' in msg or 'chat_not_found' in msg:
                res = {'status': 'unavailable', 'chat_id': normalized, 'error': str(e)}
                results[key] = res
                _cache_set(user_id, key, res)
                alert_text = f"[ALERT] Bot has no access to chat {normalized}: {e}. Додайте бота або надайте invite link."
                # notify via logger (subscription_system should pass a logger that also alerts admins)
                if logger:
                    try:
                        logger(alert_text)
                    except Exception:
                        pass
                continue
            # Too many requests or other API errors -> return unavailable with error
            if 'too many requests' in msg:
                res = {'status': 'unavailable', 'chat_id': normalized, 'error': str(e)}
                results[key] = res
                # do not cache heavy errors for long
                _cache_set(user_id, key, res)
                continue
            # Other errors
            res = {'status': 'unavailable', 'chat_id': normalized, 'error': str(e)}
            results[key] = res
            _cache_set(user_id, key, res)
        except Exception as e:
            res = {'status': 'unavailable', 'chat_id': normalized, 'error': str(e)}
            results[key] = res
            _cache_set(user_id, key, res)

    return results



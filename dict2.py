"""This module provides key-value store functions implemented on Redis"""

import logging
import os
import pickle

import redis

logging.basicConfig(
    format="%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.DEBUG,
)

logger = logging.getLogger("dict2")


def dlog(*arg):
    logger.debug(arg)


try:
    REDIS_URL = os.environ.get("REDIS_URL")
    assert REDIS_URL
    R = redis.from_url(REDIS_URL)
except redis.ConnectionError:
    dlog("Redis ConnectionError")

# For now, hard code this, as data will be stored per-user.
# Later, make this a class, with dict as a private member that will be initialized by a constructor
WHICHDICT: str = os.environ.get("WHICHDICT")
assert WHICHDICT  # should be set in environment

# Examples of how to use Redis's hset, hget, and set functions.

# r.hset("NumberVsString", "3", "Three")
# print(r.hget("NumberVsString", "3"))

# r.sadd("whitelist", "HIGH")
# print(r.scard("whitelist"))
# print(r.smembers("whitelist"))
# r.srem("whitelist", "PRE-K")


def dict_set(key, value):
    """Set the value for key and return same value, to allow something like threading"""
    global R
    # like last_value = dict_set('last_value', value)
    dumped = pickle.dumps(value)
    try:
        R.hset(WHICHDICT, key, dumped)
        return value
    except redis.RedisError:
        return None


def dict_get(key):
    """Get the value for key and return same value"""
    global R
    result = None
    try:
        got = R.hget(WHICHDICT, key)
        if got is not None:
            try:
                result = pickle.loads(got)
            except pickle.PickleError:
                result = None
        else:
            result = None
    except redis.RedisError:
        result = None
    return result


def dict_default(key, default):
    """Return key's value, if set, or the default that was passed in"""
    result = dict_get(key)
    if result is None:
        result = default
        dict_set(key, default)
    return result


def dict_init_default(key, value):
    """set the value for key, if not set yet; then return same value"""
    value = dict_default(key, value)
    return dict_set(key, value)


# Using the above functions instead of Redis set primitives:


def set_members(setname):
    """return set members"""
    result = dict_get(setname)
    return result


def set_add(setname, item):
    """add item to setname and return the resulting set"""
    temp = dict_get(setname)
    temp.add(item)
    return dict_set(setname, temp)


def set_remove(setname, item):
    """remove item from the set and return the resulting set"""
    try:
        temp = dict_get(setname)
        temp.remove(item)
        return dict_set(setname, temp)
    except redis.RedisError:
        print("RedisError")
        return set()


# Using Redis set primitives:

# def set_members(setname):
#    return r.smembers(WHICHDICT+setname)

# add item to setname and return the resulting set
# def set_add(setname, item):
#    log("set_add ", setname, item)
# We store sets as lists
#    r.sadd(WHICHDICT+setname, item)
#    return r.smembers(WHICHDICT+setname)

# remove item from the set and return the resulting set
# def set_remove(setname, item):
#    log("remove", setname, item)
#    r.srem(WHICHDICT+setname, item)
#    return map(decode, r.smembers(WHICHDICT+setname))

ITEMS = [1, 2, 3, 4, 5]
SQUARED = list(map(lambda x: x ** 2, ITEMS))


def mapset(fn, the_set):
    """map a function across a set as though it were a list"""
    ls = list(the_set)
    print(ls)
    reslist = map(fn, ls)
    print(reslist)
    resset = set(reslist)
    print(resset)
    return resset


def decode(s):
    """decode a string to utf-8"""
    return str(s, "utf-8")

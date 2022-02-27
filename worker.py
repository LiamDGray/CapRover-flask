import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import List

import mechanize  # automated web browsing: get, post
import redis
from rq import Connection, Queue, Worker

import dict2 as d

logging.basicConfig(
    format="%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.DEBUG,
)

wlogger = logging.getLogger("worker")

listen = ["high", "default", "low"]

ON_HEROKU = os.environ.get("ON_HEROKU", False)

TEST_URL = os.environ.get("TEST_URL")
assert TEST_URL

REDIS_URL = os.environ.get("REDIS_URL")
assert REDIS_URL

conn = redis.from_url(REDIS_URL)
assert conn

q = Queue(connection=conn)
assert q

br = mechanize.Browser()
assert br

patt_weekday = "([A-Z][a-z]{2})"

patt_date = "([0-9]{1,2}[/][0-9]{1,2})"

patt_weekday_date_email = "([A-Z][a-z]{2}), ([0-9]{1,2}[/][0-9]{1,2})"

# returns an array of two, start and end:
patt_times = "[0-9]{1,2}[:]*[0-9]{0,2}[ap]m"

sample_prefix = "A new job is available:\r\n\r\n"

PREFIX_LENGTH = len(sample_prefix)

sample_reject_body = (
    "*When: *"
    "Wed, 5/15 6:00am - 4:45pm"
    "\r\n"
    "*Location: *"
    "ELEMENTARY"
    "\r\n"
    "*Position: *"
    "WORLD HISTORY"
    "\r\n"
    "*Employee: *"
    "Cortez, Eleuterio"
    "\r\n\r\n"
    "click here to book! <"
)

sample_body_withnotes = (
    "*When: *"
    "Wed, 12/15 1:00pm - 3:15pm"
    "\r\n"
    "*Location: *"
    "PUEBLO HIGH"
    "\r\n"
    "*Position: *"
    "WORLD HISTORY"
    "\r\n"
    "*Employee: *"
    "Cortez, Eleuterio"
    "\r\n"
    "*Notes: *"
    "Student teacher"
    "\r\n"
    "click here to book! <"
)

sample_suffix = ">"

discard_suffix = (
    "\r\n\r\n"
    "----------------------------------\r\n\r\n"
    "Click here to *TURN OFF* future email job alerts\r\n"
    "<https://www.subalert.com/account/email_alerts/disable/152544/otCypMVsMIT8B4iN0QBIt8gDHn3IOFq8AX0XWL_x>\r\n\r\n"
    "Please Note: SubAlert not affiliated with Frontline Education™ or your\r\n"
    "school district in any way. We are an independent, 3rd party service.\r\n"
)

SUFFIX_LENGTH = len(discard_suffix)

sample_reject_email = sample_reject_body + TEST_URL + sample_suffix

sample_multiday_body = (
    "*When: *"
    "Wed, 11/10 8:00am - Thu, 11/11 3:15pm"
    "\r\n"
    "*Location: *"
    "PUEBLO HIGH"
    "\r\n"
    "*Position: *"
    "WORLD HISTORY"
    "\r\n"
    "*Employee: *"
    "Cortez, Eleuterio"
    "\r\n\r\n"
    "click here to book! <"
)

sample_multiday_email = sample_multiday_body + TEST_URL + sample_suffix

rejectParsed = (
    False,
    ["5/15"],
    6.0,
    16.75,
    10.75,
    "ELEMENTARY",
    "WORLD HISTORY",
    "Cortez, Eleuterio",
    "",
    "http://fake-subalert.herokuapp.com/book.html",
)

multidayParsed = (
    True,
    ["11/10", "11/11"],
    8.0,
    15.25,
    7.25,
    "PUEBLO HIGH",
    "WORLD HISTORY",
    "Cortez, Eleuterio",
    "",
    "http://fake-subalert.herokuapp.com/book.html",
)

sample_acceptable_body = (
    "*When: *"
    "Wed, 12/15 3:00pm - 3:15pm\r\n"
    "*Location: *"
    "UNIVERSITY HIGH\r\n"
    "*Position: *"
    "COMPUTER SCIENCE\r\n"
    "*Employee: *"
    "Smiley, Guy\r\n\r\n"
    "click here to book! <"
)

acceptableParsed = (
    False,
    ["12/15"],
    15.0,
    15.25,
    0.25,
    "UNIVERSITY HIGH",
    "COMPUTER SCIENCE",
    "Smiley, Guy",
    "",
    "http://fake-subalert.herokuapp.com/book.html",
)

sample_acceptable_email = sample_acceptable_body + TEST_URL + sample_suffix

sample_notes_email = sample_body_withnotes + TEST_URL + sample_suffix


def ParseTime(date_string: str):
    try:
        ptime = datetime.strptime(date_string, "%I:%M%p")
    except ValueError:
        ptime = datetime.strptime(date_string, "%I%p")
    return ptime


# takes theTime as time (a float, "seconds since the epoch") and converts to a float "time of day"
def hourfloat(theTime) -> float:
    theHour: float = theTime.hour + (theTime.minute / 60)
    return theHour


# Extract data from an email from alerts@subalert.com.
# Consider using regex to parse, as that's easier to read.
def extract_data_email(txt: str):
    s = txt.split("*")
    when = s[2].split("\r")[0]
    location = s[4].split("\r")[0]
    position = s[6].split("\r")[0]
    tail = s[8].split("\r")
    # use regex here to look for notes?
    employee = tail[0]
    if tail[1] and tail[1] == "Notes":
        notes = tail[2]
        nextIndex = 3
    else:
        notes = ""
        nextIndex = 2
    url = tail[nextIndex].split("<")[1].split(r">")[0]

    # log(when, location, position, employee, notes, url)

    # weekday_date = re.findall(patt_weekday_date_email, when)
    # log(weekday_date)

    dates = re.findall(patt_date, when)
    # log(when, dates)
    if len(dates) > 1:
        multiday = True
    else:
        multiday = False
    # log("multiday: ", multiday)
    times = re.findall(patt_times, when)
    # log(times)
    start_time = times[0]
    end_time = times[1]
    # log(start_time, end_time)
    stime = ParseTime(start_time)
    etime = ParseTime(end_time)
    # stime, etime are datetime objects
    # log(stime, etime)
    minutes = (etime - stime) / timedelta(minutes=1)
    hours: float = minutes / 60
    school = location
    subject = position
    teacher = employee

    results = (
        multiday,
        dates,
        hourfloat(stime),
        hourfloat(etime),
        hours,
        school,
        subject,
        teacher,
        notes,
        url,
    )
    # log(results)
    return results


# https://stackoverflow.com/questions/44133947/google-calendar-api-check-for-conflicts

# to find the first URL from an input string

patt_url = r"http[s]?://[^ >]+"


def FindURL(string: str):
    # finds the first url bracketed by <>
    # log(sample_url)
    # log(patt_url)
    urls = re.findall(patt_url, string)
    return urls[0]  # first of URLs found


default_blacklist = {
    "No Employee Certified",  # usually bad because no lesson plan
    "INTERVENTION",
    "EX ED",
    "EXCEPTIONAL",
    "PHYSICAL EDUCATION",
}
blacklist = default_blacklist

# return true if blacklist assignment found, false otherwise
# the intention is this function is called only if Swiperight returns False


def Blacklist(string: str):
    for term in blacklist:
        if re.search(term, string):
            return True
    return False


default_favorites = {
    "Herring, David",  # CS at University High
    "Valenzuela, Susana",  # CS at Tucson High Magnet
    #    'Christian, Andrew',    # CS at Sahuaro High
}

favorites = default_favorites

last_body = "default"


def Swiperight(string: str):
    for term in favorites:
        if re.search(term, string):
            return True
    return False


fave_schools = {
    "UNIVERSITY HIGH",  # 10/10
    "PUEBLO HIGH",  # 4/10, close, no passes
    "TUCSON HIGH MAGNET",  # 5/10, close, huge, no key, too few monitors
    "RINCON HIGH",  # 4/10, near Laura/Dad, don't remember the atmosphere
    "INNOVATION TECH",  # unrated but sorta near and no sports = no jocks?
}

# selector for ordered list ("ol") for TUSD high schools:
# #Search-react-component-cbd0b3d3-e2f6-4fb1-9143-521f809a17a6 > div > div.list-map-ad.clearfix > div.list-column > section > ol

# full Xpath for Greatschools rating:
# /html/body/div[5]/div/div/div[3]/div[1]/section/ol/li[1]/span[1]/div/span/div[1]/text()

fave_subjects = {
    # subjects:
    "PHYSICS",
    "12",
    "AP",
    "YOGA",
    "QIGONG",
}

default_whitelist = fave_schools  # .union(fave_subjects)

whitelist = default_whitelist

# return true if whitelist assignment found, false otherwise


def Whitelist(string: str):
    for term in whitelist:
        if re.search(term, string):
            return True
    return False


# init the values for all the keys (if not set, set them)


def init_dict():
    global favorites, whitelist, blacklist, default_favorites, default_whitelist, default_blacklist, last_body
    favorites = d.dict_init_default("favorites", default_favorites)
    whitelist = d.dict_init_default("whitelist", default_whitelist)
    blacklist = d.dict_init_default("blacklist", default_blacklist)
    last_body = d.dict_init_default("last_body", "empty default body")
    return (favorites, whitelist, blacklist, last_body)


def clean_dict_key(s: str):
    #   log(s)
    s = s.lower()
    return str(s)


def AcceptUrl(url: str, test: bool):
    global br
    wlogger.debug("in AcceptUrl with url = " + url)
    if True:  # (
        #    re.search("subalert", url)
        #    or re.search("fake-subalert", url)
        #    or re.search("localhost", url)
        # ):

        if test:
            url = TEST_URL  # HACK 12/15/21
        else:
            wlogger.debug("not a test")

        # notification is from SubAlert or my dev process
        wlogger.debug("about to open url: " + url)
        br.open(url)
        response = str(br.response().read())
        wlogger.debug("response from open: " + response)
        # How many forms does it have? If zero, it's expired; otherwise click Yes
        if len(br.forms()) > 0:
            frm = br.select_form(nr=0)  # first form is the Yes form
            wlogger.debug(frm)
            req = br.submit(label="Yes")
            if not req:
                wlogger.debug("req undefined")
                return False
            response = str(br.response().read())
            if re.search("Invalid or Expired", response):
                wlogger.debug("Invalid or Expired -- after I loaded the Yes/No forms")
                return False  # i.e. we didn't book it
            else:  # I think it says "Congratulations"
                wlogger.debug("not expired; response from submit: " + response)
                return True  # not expired yet; we got it!
        else:
            wlogger.debug("0 forms; expired before I got here")
            return False  # we didn't book it
    else:
        return False  # nothing to book


def Duration_ok(hours: float):
    # or (done_by(dates[0]) + 1 <= start_time) or (end_time+1<=start_at(today)):
    if True:  # (hours > 4):
        return True
    else:
        return False


# Queue the Accept closures into "request priority queue" so that
# current favorite assignment is accepted first

# load the load the assignment's Yes/No page (at SubAlert only) and click Yes
# return True if able to book it, False otherwise


# not sure if this function was a good idea or should go back inline into process_assignment:


def StudentTeacher(notes: str) -> bool:
    foldedNotes = notes.casefold()
    if re.search("student teacher", foldedNotes):
        return True
    else:
        return False


def test_assignment(
    body: str,
    multiday: bool,
    dates: List[str],
    start_time: float,
    end_time: float,
    hours: float,
    school: str,
    subject: str,
    teacher: str,
    notes: str,
) -> bool:  # ignoring teacher for now!
    if Whitelist(school) or StudentTeacher(
        notes
    ):  # and (start_time >= 12) and (hours <= 2)  # (not multiday) and (Whitelist(body) and (not Blacklist(body))): # and Duration_ok(hours)):
        wlogger.debug(
            "acceptable: whitelisted school or student teacher"
        )  # , afternoon, hours <= 2")
        return True
    else:
        today = date.today().strftime("%-m/%-d")
        # print("today is " + today)
        # print("start_time is " + str(start_time))
        if (
            dates[0] == today
            and (start_time >= 12)
            and Whitelist(
                school
            )  # ((school == "PUEBLO HIGH") or (school == "TUCSON HIGH MAGNET"))
            and (hours <= 3)
        ):
            wlogger.debug("acceptable: today, afternoon, nearby high school, hours <=3")
            return True
        else:
            wlogger.debug("not acceptable")
            return False


# 12/9 better test function:
# If not multiday and:
#   school is University High and subject is not PE
#   or
#   date is today and time is afternoon and school is (magnet or pueblo) and duration <= 2hrs

# Can be called from test_command or from email rx.
# return True if met acceptance criteria, False if not

# as of 11/10/21 at 2:25pm this seems to work except for weekday_date; see that part of extract_data_email
def process_assignment_email(body: str, test: bool) -> bool:
    wlogger.debug("in process_assignment_email with body: ")
    wlogger.debug(body)
    parsed = (
        multiday,
        dates,
        start_time,
        end_time,
        hours,
        school,
        subject,
        teacher,
        notes,
        url,
    ) = extract_data_email(body)

    # teacher has name in form: "Last, First"
    if test_assignment(
        body,
        multiday,
        dates,
        start_time,
        end_time,
        hours,
        school,
        subject,
        teacher,
        notes,
    ):
        # log("Acceptance criteria met")
        if AcceptUrl(url, test):
            wlogger.debug("Accepted ")
            wlogger.debug(parsed)
        else:
            wlogger.debug("Not accepted (probably too late)")
        return True
    else:
        wlogger.debug("Assignment did not meet criteria")
        return False
    return False


def simple_test(body: str, test: bool):
    p = re.compile("HIGH")
    if p.search(body):
        url = FindURL(body)
        AcceptUrl(url, test)


def process_multi(body: str, test: bool):
    s = re.split(r"--+", body)
    for assignment in s:
        # process_assignment_email(assignment, test)
        simple_test(assignment, test)


if __name__ == "__main__":
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()

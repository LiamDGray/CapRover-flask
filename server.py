# To do:
#
# -Implement minimal automated tests which trigger the webhook, especially:
#   1. Assignment to book
#   2. Assignment to ignore
#   3. Commands, especially add to blacklist, remove from blacklist
#
# -Echo last path (POST data)
# -Replay last path (as if received again)
# -Send last path to localhost
# -Send last path to Linode (to see if it works better there)
#
# -Add automated regression tests, at least curl for assignments to accept & not accept
#    can use the above tools
#
# -Port to node.js (JS for Puppeteer, userscripts, and testing in browser and Google Spreadsheets)
# -Move globals into a class, with one instance per user/subscriber
# -Do web scraping (with Puppeteer or Playwright, & Chromium headless)
# -Integrate a language with macros (JS?)
# -Move to an async model (node.js, probably)
# -Move to fly.io (faster)
# -Port to Rust, Go, or Lisp (faster)

# Orange Sub:
# Program to accept substitute teaching assignments automatically.
# Receives email notifications from SubAlert and "clicks" on the "Yes" button
# on the page linked from the alert.
# Who's me? Liam Gray, lgray95@alumni.cmu.edu

# Theory of operation:
# SubAlert can send Alerts via SMS and/or email.
# The email alerts arrive at same time as SMS and can be handled at lower cost, so we use these.
# We registered for alerts at our Gmail address and use a filter to forward each alert
# to a service (mailincloud) that posts it to a webhoook.
# The webhook is a route on our Flask app.
# We are hosting the app on a Heroku free dyno that sleeps.
# A dyno that doesn't sleep costs $7/month.

# standard and third-party libary modules:

import json
import logging
import os
import re
from logging.config import dictConfig

from flask import Flask, request, send_from_directory  # web backend framework

import dict2 as d  # dictionary based on Redis
import worker as w

ON_HEROKU = os.environ.get("ON_HEROKU")

PORT = os.environ["PORT"]
assert PORT

TEST_URL = os.environ.get("TEST_URL")
assert TEST_URL

app = Flask(__name__, static_url_path="/")

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            }
        },
        "root": {"level": "DEBUG", "handlers": ["wsgi"]},
    }
)

slogger = logging.getLogger("server")

slogger.debug("test")


@app.route("/robots.txt")
@app.route("/sitemap.xml")
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])


@app.route("/")
def home():
    slogger.debug("GET /")
    return "Hello from server.py at port " + str(PORT) + "\r\n"


@app.route("/last_body", methods=["GET"])
def getLastBody():
    last_body = str(d.dict_get("last_body"))  # last_body saved in dict
    if last_body:
        slogger.debug(last_body)
    else:
        slogger.debug("no last_body in route /last_body")
    return "last_body: \r\n" + last_body + "\r\n"


@app.route("/replay", methods=["GET"])
def replay():
    last_body = str(d.dict_get("last_body"))  # last_body saved in dict
    if last_body:
        w.q.enqueue(
            w.process_multi,
            last_body,
            True,  # test=True; don't hit the real subalert server with same URL already used.
        )  # perhaps accept commands later?
    else:
        slogger.debug("no last_body in route /replay")
    return "replayed receipt of last_body: " + last_body + "\r\n"


# not currently used:
def email2webhook():  # this is for cloudmailin
    jsonData = request.get_json()
    if jsonData:
        #        app.logger.info(jsonData)
        body = jsonData["plain"]
        if body:
            r = re.compile("TESTFOO")
            if r.search(body):
                slogger.debug("found TESTFOO")
                test = True
            else:
                test = False
            w.simple_test(
                body, test
            )  # this will accept the assignment if meets simple criteria
            slogger.debug(body)
            d.dict_set("last_body", body)
    return json.dumps({"success": True}), 200, {"ContentType": "application/json"}


@app.route("/email", methods=["POST"])
@app.route("/multiple", methods=["POST"])
def multiple_jobs():
    jsonData = request.get_json()
    if jsonData:
        body = jsonData["plain"]
        if body:
            p = re.compile("TESTFOO")
            if p.search(body):
                test = True
            else:
                test = False
            w.q.enqueue(w.process_multi, body, test)
            slogger.debug(body)
            d.dict_set("last_body", body)

    return json.dumps({"success": True}), 200, {"ContentType": "application/json"}


# w.q.enqueue(w.process_assignment_email, w.sample_acceptable_email, True)


@app.route("/test", methods=["GET"])
def test_asserts():
    # asserts here
    assert w.rejectParsed == w.extract_data_email(w.sample_reject_email)
    assert w.multidayParsed == w.extract_data_email(w.sample_multiday_email)
    assert w.acceptableParsed == w.extract_data_email(w.sample_acceptable_email)
    assert w.TEST_URL == w.FindURL(w.TEST_URL + "  " + w.TEST_URL)
    assert w.TEST_URL == w.FindURL(w.sample_reject_email)
    assert w.Blacklist("INTERVENTION")
    assert not w.Blacklist("COMPUTER SCIENCE")
    assert w.Swiperight("Herring, David")
    assert w.Whitelist("UNIVERSITY HIGH")
    assert "whitelist" == w.clean_dict_key("WHITELIST")
    assert w.Duration_ok(15.0)
    assert w.AcceptUrl(TEST_URL, True)
    assert w.AcceptUrl(TEST_URL, False)
    assert not w.StudentTeacher("foobar")
    assert w.StudentTeacher("STUDENT TEACHER")
    assert w.test_assignment(
        "",
        False,
        ["12/15"],
        12,
        15.25,
        3.25,
        "PUEBLO HIGH",
        "WORLD HISTORY",
        "Cortez, Eleuterio",
        "student teacher",
    )

    assert not w.test_assignment(
        "",
        False,
        ["12/15"],
        7,
        14.25,
        7.25,
        "ELEMENTARY",
        "WORLD HISTORY",
        "Cortez, Eleuterio",
        "",
    )
    assert not w.process_assignment_email(w.sample_reject_email, True)
    assert w.process_assignment_email(w.sample_acceptable_email, True)

    return json.dumps({"success": True}), 200, {"ContentType": "application/json"}


# test_asserts()

if __name__ == "__main__":  # Running eg `python server.py`
    w.init_dict()
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    app.logger.addHandler(stream_handler)
    app.run(host="0.0.0.0", port=PORT)  # ssl_context=('cert.pem', 'key.pem'))

else:  # Running in Foreman / heroku
    w.init_dict()
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    app.logger.addHandler(stream_handler)

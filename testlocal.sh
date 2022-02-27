#!/usr/bin/bash

export PORT=5000
export REDIS_URL=redis://localhost:6379
export TEST_URL=http://fake-subalert.herokuapp.com/book.html
export TZ=America/Phoenix
export WHICHDICT=liamdgray

python server.py &
python worker.py & # this is also imported by server.py but task dequeue happens only when run as main
sleep 2

#test the fake booking server:
#curl TEST_URL

#test the asserts:
#curl http://localhost:5000/test

#server.py in heroku local runs at port 5000:
curl -H "Content-Type: application/json" --data @sample.json http://localhost:5000/email

#test server.py email webhook with sample json:
#curl -H "Content-Type: application/json" --data @multiple.json http://localhost:5000/multiple

#can replay last POST to /email using a GET:
#curl http://localhost:5000/replay

sleep 5

pgrep python | xargs kill -9
pgrep gunicorn | xargs kill -9

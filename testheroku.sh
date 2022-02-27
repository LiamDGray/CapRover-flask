#!/usr/bin/bash

#test the fake booking server, fake-subalert:
#curl http://fake-subalert.herokuapp.com/book.html
#curl http://fake-subalert.herokuapp.com/submit

printf "\n/test: "
curl https://fast-ocean-54917.herokuapp.com/test

printf "\n/email: "
curl -H "Content-Type: application/json" --data @sample.json https://fast-ocean-54917.herokuapp.com/email

printf "\n/multiple: "
curl -H "Content-Type: application/json" --data @multiple.json https://fast-ocean-54917.herokuapp.com/multiple

printf "\n/replay: "
curl https://fast-ocean-54917.herokuapp.com/replay

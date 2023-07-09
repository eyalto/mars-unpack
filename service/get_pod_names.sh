#!/usr/bin/env bash

export WEBAPP_POD=$(kubectl get -l="app=unpacker-app" pod --output=jsonpath='{.items[0].metadata.name}')
export CONSUMER_POD=$(kubectl get -l=app="unpacker-service" pod --output=jsonpath='{.items[0].metadata.name}')

echo "WEBAPP_POD $WEBAPP_POD"
echo "CONSUMER_POD $CONSUMER_POD"

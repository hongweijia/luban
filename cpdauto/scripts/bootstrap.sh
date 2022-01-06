#!/bin/bash


##### "Main" starts here
SCRIPT=${0##*/}

echo $SCRIPT

#cd /ibm
# Make sure there is a "logs" directory in the current directory
if [ ! -d "${PWD}/logs" ]; then
  mkdir logs
  rc=$?
  if [ "$rc" != "0" ]; then
    # Not sure why this would ever happen, but...
    # Have to echo here since trace log is not set yet.
    echo "Creating ${PWD}/logs directory failed.  Exiting..."
    exit 1
  fi
fi

LOGFILE="${PWD}/logs/${SCRIPT%.*}.log"

mkdir -p templates
chmod +x ${PWD}/*
#chmod +x ${PWD}/cpd_install.py
echo $HOME
#echo $PATH
${PWD}/cpd_install.py

#!/bin/bash
set -e

echo "Waiting 30 seconds before starting commander..."
sleep 30

echo "Starting commander.py via supervisorctl..."
supervisorctl start commander

echo "Commander startup initiated"

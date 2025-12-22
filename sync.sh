#!/bin/bash

LOCAL_DIR="/Users/mkremnev/Project/i@mkremnev/forex-signal-agent"
REMOTE_USER="root"
REMOTE_HOST="217.29.63.98"
REMOTE_DIR="/root/forex_ds"

rsync -avz --delete $LOCAL_DIR $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR

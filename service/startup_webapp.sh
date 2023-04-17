#!/bin/bash

google-drive-ocamlfuse -config config.fuse /mnt/gdrive

python3 main_webapp.py
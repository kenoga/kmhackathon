# -*- coding: utf-8 -*-

import argparse
import requests
from send import send

url = 'https://cm-hackathon-s-rmomo63.c9users.io/test'

parser = argparse.ArgumentParser()

parser.add_argument('state', choices=['free', 'busy'])
parser.add_argument('--minute', type=int)
parser.add_argument('--hour' , type=int)
args = parser.parse_args()

send(args.state)
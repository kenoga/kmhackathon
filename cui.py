# -*- coding: utf-8 -*-

import argparse
import requests

url = 'https://cm-hackathon-s-rmomo63.c9users.io/test'

parser = argparse.ArgumentParser()

parser.add_argument('state', choices=['free', 'busy'])
parser.add_argument('--minute', type=int)
parser.add_argument('--hour' , type=int)
args = parser.parse_args()

payload = {}
if args.state == 'free':
    payload['color'] = 'blue'
    payload['text'] = 'I\'m free.' 
elif args.state == 'busy':
    payload['color'] = 'red'
    payload['text'] = 'I\'m busy.'

r = requests.get(url=url, params=payload)

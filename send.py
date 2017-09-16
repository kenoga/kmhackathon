# -*- coding: utf-8 -*- 

import requests

def send(state):
    payload = {}
    url = 'https://cm-hackathon-s-rmomo63.c9users.io/test'
    
    if state == 'free':
        payload['state'] = 'free'
    elif state == 'busy':
        payload['state'] = 'busy'
    
    r = requests.get(url=url, params=payload)
    

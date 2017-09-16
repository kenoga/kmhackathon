# -*- coding: utf-8 -*-

import ConfigParser
from speech.inputter import SpeechInputter
from Queue import Queue
from send import send

# load config
conf_file_path =  './speech/conf.ini'
conf = ConfigParser.SafeConfigParser()
conf.read(conf_file_path)

si = SpeechInputter(conf)
q = Queue()
si.set_q(q)

si.start()
while True:
    result = q.get()
    if 'recog_result' in result:
        utt = result['recog_result']

        if u'暇' in utt:
            send('free')
        elif u'忙' in utt:
            send('busy')

# -*- coding: utf-8 -*-

import sys, os, signal
import argparse, ConfigParser

from google.cloud import speech
import asr.audio_stream as ast
import asr.result_watcher as rw
import threading
import queue


class SpeechInputter(threading.Thread):
    '''
    音声入力器
    .start()で別スレッドで音声入力を受付開始する
    別スレッド内では，音声認識結果が得られたらキューに文字列を追加して入力受付を再開する
    元スレッドでq.get()しておけば音声認識結果が返ってきたときに何らかの処理を行わせることができる
    '''
    
    def __init__(self, conf):
        super(SpeechInputter, self).__init__()
        self.q = None
        
        self.sample_rate = conf.getint("pyaudio", "sample_rate")
        self.result_watcher = rw.CombinedResultWatcher()
        # 標準出力のタイプを確認
        if conf.get('output', 'stdout_output_type') == 'display':
            self.result_watcher.add_watcher(rw.StdoutResultWatcherForDisplay())
        elif conf.get('output', 'stdout_output_type') == 'analysis':
            self.result_watcher.add_watcher(rw.StdoutResultWatcherForAnalysis())
        else:
            self.result_watcher.add_watcher(rw.StdoutResultWatcher())
            
        self.client = speech.Client()
        chunk_size = conf.getint('pyaudio', 'chunk_size')
        logpower_thresh = conf.getfloat('pyaudio', 'logpower_thresh')
        timeout_in_sec = conf.getfloat('pyaudio', 'timeout_in_sec')
        self.audio_stream = ast.PyAudioStream(self.sample_rate,
                                         chunk_size=chunk_size,
                                         logpower_thresh=logpower_thresh,
                                         timeout_in_sec=timeout_in_sec)

    def set_q(self, q):
        self.q = q
    
    def listen_print_loop(self, client, audio_stream, result_watcher=None):
        # 一発話全体の音声データ（音素アライメントとピッチ計算に利用）
        audio_data = b''
        # 最終声認識結果
        recognition_result = ''

        audio_stream.start()

        with audio_stream.cond:
            while not audio_stream.vad_started:
                audio_stream.cond.wait()
        
        self.q.put({'type': 'recog_start'})
        sample = client.sample(stream=audio_stream,
                               encoding=speech.Encoding.LINEAR16,
                               sample_rate_hertz=self.sample_rate)
        results = sample.streaming_recognize(
            interim_results=True,
            single_utterance=audio_stream.single_utterance_required,
            language_code='ja-JP',
            max_alternatives=1
        )
        # 認識開始を通知
        if result_watcher is not None:
            result_watcher.notify_start(audio_stream.audio_id)
            
        recognition_result = ''
        for result in results:
            audio_stream.ping()
            
            if result_watcher is not None:
                result_watcher.notify_interim_result(audio_stream.audio_id,
                                                     recognition_result +
                                                     result.alternatives[0].transcript)
            if result.is_final:
                if len(recognition_result) > 0:
                    recognition_result += u'、'
                recognition_result += result.alternatives[0].transcript
                if audio_stream.single_utterance_required:
                    audio_stream.finish_vad()
        audio_stream.stop()
        audio_data = audio_stream.get_data()
                
        if result_watcher is not None:
            result_watcher.notify_finish(audio_stream.audio_id, recognition_result, [], [], [], [])
        if recognition_result and self.q:
            self.q.put({'type': 'recog_result', 'recog_result': recognition_result})
        else:
            self.q.put({'type': 'recog_end'})
        
        
    def run(self):
        while not self.audio_stream.closed:
            try:
                self.listen_print_loop(self.client, self.audio_stream, self.result_watcher)
            except RuntimeError as e:
                print "NON FATAL ERROR:", e.message

    def get(self):
        # block
        text = self.q.get()
        return text
        
    def is_empty(self):
        return self.q.empty()

class TestInputter(threading.Thread):
    
    def __init__(self, conf):
        super(TestInputter, self).__init__()
    
    def set_q(self, q):
        self.q = q
        
    def run(self):
        while True:
            print('INPUT:')
            s = raw_input()
            s = s.strip().decode('utf-8')
            if s:
                self.q.put({'type': 'recog_result', 'recog_result':s})
            
    def get(self):
        # block
        text = self.q.get()
        return text
        
    def is_empty(self):
        return self.q.empty()



class TextInputter(object):
    def __init__(self, conf):
        pass
    
    def start(self):
        pass
    
    def get(self):
        while True:
            print "INPUT: ",
            text = raw_input()
            if text.strip():
                return text
                


def test():
    conf_file_path =  "./asr/conf.ini"
    conf = ConfigParser.SafeConfigParser()
    conf.read(conf_file_path)
    speech_inputter = SpeechInputThread(conf)
    speech_inputter.start()
    while(True):
        text = speech_inputter.get()


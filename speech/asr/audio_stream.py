# encoding: utf-8
from abc import ABCMeta, abstractmethod
import threading
import struct

import pyaudio
import numpy as np
import time
import wave
from os import path

class AudioStream(object):
    u"""
    AudioStreamはsample.stream_recognizeに対するstream（readメソッド経由）としてか，
    sync_recognizeに対するcontent（get_dataメソッド経由）として利用する．

    stream_recognizeによる認識の場合は以下のように実行される．

    (1) audio_stream.start()が呼ばれる．
    (2) audio_stream.vad_started が True になるまで待つ．
    (3) client.sample(stream=audio_stream, ...) が呼ばれ，認識が開始される．
    (4) 結果を待つ．audio_stream.read() が None を返すとループを break する．
    (5) audio_stream.ping() が呼ばれる．
    (6) audio_stream.single_utterance_required が True の場合は，is_final が True の認識結果が
        得られたら audio_stream.finish_vad() が呼ばれる．
    (7) (4)に戻る．
    (8) audio_stream.stop() が呼ばれる．
    (9) audio_stream.get_data() が呼ばれ，1発話分の音声全体が取得される．

    以上より，stream_recongizeによる認識を行うためには以下を満たす必要がある．

    A. start() でVAD開始の待機状態になる機能．
    A. VADの開始を自ら検知し，通知をする機能．
       （ロックや通知は audio_stream.cond を通じて行うこと）
    B-1. VADの終了を自ら検知し，read() メソッドで None を返す機能，もしくは
    B-2. single_utterance_required が True で，finish_vad()メソッドが呼ばれることによって
         以降の read() メソッドで None を返す機能．
    C. stop() メソッドで一旦全てを中断し，VAD開始からVAD終了までの音声データを get_data() 
       メソッドで返す機能．
    D. （オプション）ping() メソッドがある閾値以上の間呼ばれなかった場合に，自身の
       finish_vad()メソッドを呼び，認識をキャンセルする機能．
       本機能は，stream_recognizeにおいて，開始から一定時間（4秒前後?）認識結果が出ないまま
       放置するとその後の処理がストールすることがある（Google側のバグ?）ための応急処置である．

    sync_recognizeによる認識の場合は以下のように実行される．

    (1) audio_stream.start() が呼ばれる．
    (2) audio_stream.read() がNoneを返すまで呼ばれる．
    (3) audio_stream.stop() が呼ばれる．
    (4) audio_stream.get_data() が呼ばれ，音声データが取得される．

    以上より，sync_recognizeによる認識を行うためには，VADの開始，終了を自ら宣言できる
    必要がある．
    """
    __metaclass__ = ABCMeta

    def __init__(self):
        self._audio_id = 0
        self.__cond = threading.Condition()
        self.__vad_started  = False
        self.__vad_finished = False
        
    @property
    def single_utterance_required(self):
        u"""
        stream_recognizeを呼ぶ時にsingle_utteranceをTrueにする必要があるかどうか．
        streamの責任でVADを行わない場合はTrueにする必要がある．
        """
        return False

    @property
    def sync_mode_enabled(self):
        u"""
        sync_recognizeに対応しているかどうか
        """
        return True

    @property
    def closed(self):
        u"""
        機能が停止しているかどうか．
        stream_recognizeとの互換性をとるためのプロパティ．
        """
        return False
    
    @property
    def audio_id(self):
        u"""
        現在のAudio ID（何発話目か）
        """
        return self._audio_id

    @property
    def cond(self):
        u"""
        状態変化，データの読み書きが行われた時に通知を行うための Condition インスタンス
        """
        return self.__cond
    
    @property
    def vad_started(self):
        u"""VADが開始しているかどうか"""
        return self.__vad_started

    @vad_started.setter
    def vad_started(self, value):
        self.__vad_started = value

    @property
    def vad_finished(self):
        u"""VADが終了しているかどうか"""
        return self.__vad_finished

    @vad_finished.setter
    def vad_finished(self, value):
        self.__vad_finished = value
        
    @abstractmethod
    def start(self):
        u"""録音を開始（再開）する．過去のデータは捨てられる"""
        pass

    @abstractmethod
    def stop(self):
        u"""録音を停止する"""
        pass

    @abstractmethod
    def close(self):
        u"""全機能を停止する．再開はできない"""
        pass

    @abstractmethod
    def read(self, size):
        u"""データをsizeバイト分読み込む．データが無い場合はNoneを返す"""
        pass

    @abstractmethod
    def get_data(self):
        u"""過去に読み込んだデータを取得する"""
        pass

    def ping(self):
        u"""認識中に結果が届いたことを通知する"""
        return

    def start_vad(self):
        u"""VADの開始を宣言"""
        return
        
    def finish_vad(self):
        u"""VADの終了を宣言"""
        return


class PyAudioStream(AudioStream):
    def __init__(self, rate, chunk_size, logpower_thresh, timeout_in_sec):
        AudioStream.__init__(self)

        self.__audio_interface = pyaudio.PyAudio()
        self.__audio_stream = self.__audio_interface.open(
            format=pyaudio.paInt16,
            channels=1, rate=rate,
            input=True, frames_per_buffer=chunk_size,
            start=False,
            stream_callback=self.read_callback
        )
        self.__logpower_thresh = logpower_thresh
        self.__timeout_in_sec = timeout_in_sec
        self.__stopped = True
        self.__buff = bytearray()
        self.__read_point = 0
        self.__last_ping_time = time.time()
        self.__closed = False

    def read_callback(self, in_data, frame_count, time_info, status):
        u"""PyAudioでオーディオフレームが読み込まれたら呼ばれるコールバック関数"""
        with self.cond:
            # print "", self.__stopped, self.vad_finished
            if self.__stopped or self.vad_finished:
                # 処理が開始されて無い，またはVAD終了状態だったら何もしない
                return None, pyaudio.paContinue
            if not self.vad_started:
                # VADが開始していない場合は，パワーを計算する
                values = struct.unpack('h' * (len(in_data) / 2), in_data)
                mean_log_power = np.log10(np.sqrt(np.mean(np.square(values))))
                # print "\r%10.5f" % mean_log_power
                if  mean_log_power < self.__logpower_thresh:
                    # パワーが閾値に到達していない場合は何もせずに終了する
                    return None, pyaudio.paContinue
                else:
                    # そうでなければVAD開始を宣言する（通知はデータ送信で行われるので，
                    # 敢えてする必要はない）
                    self.vad_started = True
                    # 最終動作確認時間を現在の時刻にする
                    self.__last_ping_time = time.time()
            # VADが開始されている場合の処理
            # バッファにデータを入れて通知して終了する
            self.__buff.extend(in_data)
            self.cond.notifyAll() 
        return None, pyaudio.paContinue

    @property
    def single_utterance_required(self):
        return True

    @property
    def sync_mode_enabled(self):
        return False

    @property
    def closed(self):
        return self.__closed

    def start(self):
        with self.cond:
            if not self.__stopped:
                return
            self.__buff = bytearray()
            self.__read_point = 0
            self.__audio_stream.start_stream()
            self.__stopped = False
            self._audio_id += 1
            self.vad_started = False
            self.vad_finished = False
            self.cond.notifyAll()

    def stop(self):
        with self.cond:
            if self.__stopped:
                return
        self.__audio_stream.stop_stream()
        with self.cond:
            self.__stopped = True
            self.cond.notifyAll() 

    def close(self):
        self.stop()
        self.__audio_interface.terminate()
        self.__closed = True

    def read(self, size):
        # VADの終了宣言がなく，ping()が一定時間きていない場合は finish_vad を呼ぶ
        if not self.vad_finished and time.time() - self.__last_ping_time > self.__timeout_in_sec:
            self.finish_vad()
        # print "CHECK-1"
        with self.cond:
            # 読み込みに必要なサイズに到達しないうちは到達するまで待つ
            while len(self.__buff) - self.__read_point < size:
                # ただし，読み込み終了（またはVAD終了）の場合は終了する．
                if self.__stopped or self.vad_finished:
                    return None
                # print "CHECK-2"
                self.cond.wait()
                # print "CHECK-3"
            # 読み込みに十分なサイズがあるはず
            data = bytes(self.__buff[self.__read_point:(self.__read_point + size)])
            self.__read_point += size
        # print len(self.__buff)
        return data

    def get_data(self):
        return bytes(self.__buff)

    def ping(self):
        self.__last_ping_time = time.time()
        
    def start_vad(self):
        u"""外部からVAD開始を宣言する（このオブジェクトでは呼ばれない）"""
        with self.cond:
            self.vad_started = True
            self.cond.notifyAll()
            
    def finish_vad(self):
        with self.cond:
            self.vad_finished = True
            self.cond.notifyAll()

class FileAudioStream(AudioStream):
    def __init__(self, filename_list_or_filename, realtime_mode=False):
        AudioStream.__init__(self)
        if isinstance (filename_list_or_filename, list):
            self.__filename_list = filename_list_or_filename
        else:
            self.__filename_list = [filename_list_or_filename]
        self.__closed = False
        self.__buff = None
        self.__read_point = 0
        self.__stopped = True
        self.__realtime_mode = realtime_mode
        
    @property
    def closed(self):
        return self.__closed

    def start(self):
        with self.cond:
            if self.closed:
                raise Exception ('already closed')
            if not self.__stopped:
                return
            
            filename = self.__filename_list[self._audio_id]
            _, ext = path.path(filename).splitext()
            if ext == '.wav':
                handle = wave.open(filename, 'r')
                self.__buff = handle.readframes(handle.getnframes())
                handle.close()
            else:
                with open(filename, 'rb') as handle:
                    self.__buff = handle.read(-1)

            self.__read_point = 0
            self.__stopped = False
            self.vad_started = True # こうしないと認識が開始されない
            self.vad_finished = False
            self._audio_id += 1
            self.cond.notifyAll()

    def stop(self):
        with self.cond:
            if self.__stopped:
                return
            self.__stopped = True

            if self._audio_id == len (self.__filename_list):
                self.__closed = True
            
            self.cond.notifyAll()

    def close(self):
        self.stop()
        self.__closed == True

    def read(self, size):
        data = None
        with self.cond:
            remaining = len (self.__buff) - self.__read_point
            if remaining > size:
                data = self.__buff[self.__read_point:(self.__read_point + size)]
                self.__read_point += size
            elif remaining > 0:
                data = self.__buff[self.__read_point:]
                self.__read_point = len (self.__buff)
            else:
                data = None

            if self.__realtime_mode and data is not None:
                time.sleep (len(data) / 2 / 16000.0)

            self.cond.notifyAll()
                
        if data is None and not self.vad_finished:
            self.finish_vad()
                
        return data

    def start_vad(self):
        with self.cond:
            self.vad_started = True
            self.cond.notifyAll()
            
    def finish_vad(self):
        with self.cond:
            self.vad_finished = True
            self.cond.notifyAll()

    def get_data(self):
        with self.cond:
            return self.__buff

if __name__ == '__main__':
    # audio_stream = MfccClientAudioStream()
    audio_stream = PyAudioStream(16000, 1600)
    while True:
        print "CHECK-1"
        audio_stream.start()
        print "CHECK-2"
        while True:
            data = audio_stream.read(160)
            if data is None:
                print "data is None"
                break
            else:
                print len(data)
        print "CHECK-3"
        audio_stream.stop()
        print "CHECK-4"
        print len(audio_stream.get_data())
        print "CHECK-5"

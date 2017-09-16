# encoding: utf-8
import sys
from abc import ABCMeta, abstractmethod

class ResultWatcher(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        pass

    @abstractmethod
    def notify_start(self, audio_id):
        pass

    @abstractmethod
    def notify_abort(self, audio_id):
        pass
        
    @abstractmethod
    def notify_interim_result(self, audio_id, result):
        pass

    @abstractmethod
    def notify_finish(self, audio_id, recognition_result,
                      phone_list, endtime_list,
                      f0_list, rms_list):
        pass

class StdoutResultWatcher(ResultWatcher):

    def __init__(self):
        ResultWatcher.__init__(self)

    def notify_start(self, audio_id):
        print "SPEECH RECOGNITION START (AUDIO ID=%d)" % audio_id
        sys.stdout.flush()

    def notify_abort(self, audio_id):
        print "SPEECH RECOGNITION ABORT (AUDIO ID=%d)" % audio_id
        sys.stdout.flush()

    def notify_interim_result(self, audio_id, result):
        if type(result) == unicode:
            result = result.encode('utf-8')
        print "\r",
        print result,
        sys.stdout.flush()

    def notify_finish(self, audio_id, recognition_result,
                      phone_list, endtime_list, f0_list, rms_list):
        if type(recognition_result) == unicode:
            recognition_result = recognition_result.encode('utf-8')
        print ''
        print "SPEECH RECOGNITION END (AUDIO ID=%d)" % audio_id
        print recognition_result        
        if len(phone_list) > 0 and len(phone_list) == len(endtime_list):
            for phone, endtime in zip(phone_list, endtime_list):
                print '%s(%d)' % (phone, endtime),
            print ''
        if len(f0_list) > 0 or len(rms_list) > 0:
            print 'SIZE OF F0 LIST=%d, SIZE OF RMS LIST=%d' % (len(f0_list), len(rms_list))
        sys.stdout.flush()

class StdoutResultWatcherForDisplay(ResultWatcher):

    def __init__(self):
        ResultWatcher.__init__(self)

    def notify_start(self, audio_id):
        print "SPEECH RECOGNITION START (AUDIO ID=%d)" % audio_id
        sys.stdout.flush()

    def notify_abort(self, audio_id):
        print "SPEECH RECOGNITION ABORT (AUDIO ID=%d)" % audio_id
        sys.stdout.flush()

    def notify_interim_result(self, audio_id, result):
        if type(result) == unicode:
            result = result.encode('utf-8')
        print "INTERIM RESULT RECEIVED (AUDIO ID=%d)" % audio_id
        print "<BEGIN RECOGNITION RESULT>"
        print result
        print ""
        print ""
        print ""
        print ""
        print "<END RECOGNITION RESULT>"
        sys.stdout.flush()

    def notify_finish(self, audio_id, recognition_result,
                      phone_list, endtime_list, f0_list, rms_list):
        if type(recognition_result) == unicode:
            recognition_result = recognition_result.encode('utf-8')

        print "FINAL RESULT RECEIVED (AUDIO ID=%d)" % audio_id
        print "<BEGIN RECOGNITION RESULT>"
        print recognition_result
        print ' '.join(phone_list)
        print ' '.join(["%d" % x for x in endtime_list])
        print ' '.join(["%g" % x for x in f0_list])
        print ' '.join(["%g" % x for x in rms_list])
        print "<END RECOGNITION RESULT>"
        sys.stdout.flush()

class StdoutResultWatcherForAnalysis(ResultWatcher):
    u"""オフライン分析のために，標準出力にシンプルな出力を行うResultWatcher"""
    def __init__(self):
        ResultWatcher.__init__(self)

    def notify_start(self, audio_id):
        pass

    def notify_abort(self, audio_id):
        pass
        
    def notify_interim_result(self, audio_id, result):
        pass

    def notify_finish(self, audio_id, recognition_result,
                      phone_list, endtime_list,
                      f0_list, rms_list):
        print audio_id
        print recognition_result
        print ' '.join(phone_list)
        print ' '.join(["%d" % x for x in endtime_list])
        print ' '.join(["%g" % x for x in f0_list])
        print ' '.join(["%g" % x for x in rms_list])
        

class CombinedResultWatcher(ResultWatcher):

    def __init__(self):
        ResultWatcher.__init__(self)

        self._watchers = []

    def add_watcher(self, watcher):
        if not isinstance(watcher, ResultWatcher):
            raise RuntimeError('given object is not a ResultWatcher')
        self._watchers.append(watcher)

    def notify_start(self, audio_id):
        for watcher in self._watchers:
            watcher.notify_start(audio_id)
        
    def notify_abort(self, audio_id):
        for watcher in self._watchers:
            watcher.notify_abort(audio_id)

    def notify_interim_result(self, audio_id, result):
        for watcher in self._watchers:
            watcher.notify_interim_result(audio_id, result)

    def notify_finish(self, audio_id, recognition_result,
                      phone_list, endtime_list, f0_list, rms_list):
        for watcher in self._watchers:
            watcher.notify_finish(audio_id, recognition_result,
                      phone_list, endtime_list, f0_list, rms_list)

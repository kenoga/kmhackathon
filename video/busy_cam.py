# -*- coding: utf-8 -*- 

import cv2
import numpy as np
import time
import requests

url ='https://cm-hackathon-s-rmomo63.c9users.io/test'

face_cascade_path = '/home/ict/.pyenv/versions/anaconda-4.0.0/pkgs/opencv-2.4.11-nppy27_0/share/OpenCV/haarcascades/haarcascade_frontalface_default.xml'
eye_cascade_path = '/home/ict/.pyenv/versions/anaconda-4.0.0/pkgs/opencv-2.4.11-nppy27_0/share/OpenCV/haarcascades/haarcascade_eye.xml'
nose_cascade_path = '/home/ict/.pyenv/versions/anaconda-4.0.0/pkgs/opencv-2.4.11-nppy27_0/share/OpenCV/haarcascades/haarcascade_mcs_nose.xml' 

face_cascade_path = 'haarcascade_frontalface_default.xml'
eye_cascade_path = 'haarcascade_eye.xml'
nose_cascade_path = 'haarcascade_mcs_nose.xml' 

face_cascade = cv2.CascadeClassifier(face_cascade_path)
eye_cascade = cv2.CascadeClassifier(eye_cascade_path)
nose_cascade = cv2.CascadeClassifier(nose_cascade_path)

def frontal_face_detection(img):

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    #if type(faces) == np.ndarray:
    #    return True
    #else:
    #    return False
    ### 目二つと鼻一つの検出 ###
    is_frontal_face = False
    for (x, y, w, h) in faces:
        roi_gray = gray[y:y+h, x:x+w]
        roi_color = img[y:y+h, x:x+w]
        eyes = eye_cascade.detectMultiScale(roi_gray)
        noses = nose_cascade.detectMultiScale(roi_gray)
        if type(eyes) == np.ndarray and type(noses) == np.ndarray:
            if len(eyes[0]) >= 2 and len(noses[0]) >= 1:
                is_frontal_face = True
                break
    return is_frontal_face

def send_query(query='free'):
    payload = {'state':query}
    requests.get(url, params=query)


def main(interval=0.1 ,span=60, border=0.5):
    cap = cv2.VideoCapture(0)

    cycle = 0
    detected_count = 0

    while True:
        time.sleep(interval)

        cap.grab()
        ret, frame = cap.read()

        cycle += 1
        if frontal_face_detection(frame):
            detected_count += 1
            print('detected')
        else:
            print('Nothing')

        if cycle % span == 0:
            if detected_count > border*span:
                send_query('busy')
            else:
                send_query('free')
            cycle = 0
            detected_count = 0

        cv2.imshow('camera capture', frame)

if  __name__=='__main__':
    main()

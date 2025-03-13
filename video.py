import cv2

cap = cv2.VideoCapture("/dev/video0")
_,frame=cap.read()
cv2.imshow("asd",frame)
cv2.waitKey(0)
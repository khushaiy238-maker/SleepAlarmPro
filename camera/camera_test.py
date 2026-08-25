import cv2

cap = cv2.VideoCapture(0)

while True:

    success, frame = cap.read()

    if not success:
        break

    # Flip horizontally
    frame = cv2.flip(frame, 1)

    cv2.imshow("Sleep Alarm Pro Camera", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
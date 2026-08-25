import cv2
import mediapipe as mp

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

cap = cv2.VideoCapture(0)

while True:

    success, frame = cap.read()

    if not success:
        break

    frame = cv2.flip(frame, 1)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    results = face_mesh.process(rgb)

    status = "Face Not Found"
    color = (255, 255, 255)

    if results.multi_face_landmarks:

        face = results.multi_face_landmarks[0]

        h, w, _ = frame.shape

        # Important landmarks
        nose = face.landmark[1]
        left_face = face.landmark[234]
        right_face = face.landmark[454]
        forehead = face.landmark[10]
        chin = face.landmark[152]

        nose_x = int(nose.x * w)
        nose_y = int(nose.y * h)

        left_x = int(left_face.x * w)
        right_x = int(right_face.x * w)

        top_y = int(forehead.y * h)
        bottom_y = int(chin.y * h)

        face_center_x = (left_x + right_x) // 2
        face_center_y = (top_y + bottom_y) // 2

        dx = nose_x - face_center_x
        dy = nose_y - face_center_y

        if dx < -20:
            status = "Looking Left"
            color = (0, 255, 255)

        elif dx > 20:
            status = "Looking Right"
            color = (0, 255, 255)

        elif dy < -20:
            status = "Looking Up"
            color = (255, 0, 255)

        elif dy > 20:
            status = "Looking Down"
            color = (255, 0, 255)

        else:
            status = "Looking Forward"
            color = (0, 255, 0)

        cv2.putText(
            frame,
            status,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            color,
            2
        )

    cv2.imshow("Sleep Alarm Pro - Head Pose Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
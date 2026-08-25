import cv2
import mediapipe as mp
import math
import time
import threading
import pymysql
import os
import json
from datetime import datetime
from playsound import playsound


# ==========================================================
# SETTINGS
# ==========================================================

SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "settings.json"
)

DEFAULT_SETTINGS = {
    "alarm_sound": True,
    "ai_detection": True,
    "drowsiness_seconds": 3,
    "eye_sensitivity": "normal"
}


def load_settings():

    try:

        if not os.path.exists(SETTINGS_FILE):

            print("=" * 60)
            print("settings.json NOT FOUND")
            print("Using default settings.")
            print("=" * 60)

            return DEFAULT_SETTINGS.copy()

        with open(
            SETTINGS_FILE,
            "r"
        ) as file:

            settings = json.load(file)

        # Add missing settings automatically
        for key, value in DEFAULT_SETTINGS.items():

            if key not in settings:
                settings[key] = value

        print("=" * 60)
        print("SETTINGS LOADED")
        print(
            "Alarm Sound       :",
            settings["alarm_sound"]
        )
        print(
            "AI Detection       :",
            settings["ai_detection"]
        )
        print(
            "Drowsiness Time    :",
            settings["drowsiness_seconds"],
            "seconds"
        )
        print(
            "Eye Sensitivity    :",
            settings["eye_sensitivity"]
        )
        print("=" * 60)

        return settings

    except Exception as e:

        print("=" * 60)
        print("SETTINGS LOAD ERROR")
        print(e)
        print("Using default settings.")
        print("=" * 60)

        return DEFAULT_SETTINGS.copy()


# Load settings
settings = load_settings()

ALARM_SOUND_ENABLED = bool(
    settings.get(
        "alarm_sound",
        True
    )
)

AI_DETECTION_ENABLED = bool(
    settings.get(
        "ai_detection",
        True
    )
)

try:

    DROWSINESS_SECONDS = int(
        settings.get(
            "drowsiness_seconds",
            3
        )
    )

except:

    DROWSINESS_SECONDS = 3


if DROWSINESS_SECONDS not in [2, 3, 4, 5]:

    DROWSINESS_SECONDS = 3


EYE_SENSITIVITY = settings.get(
    "eye_sensitivity",
    "normal"
)


if EYE_SENSITIVITY not in [
    "low",
    "normal",
    "sensitive"
]:

    EYE_SENSITIVITY = "normal"


# ==========================================================
# EYE SENSITIVITY THRESHOLD
# ==========================================================

if EYE_SENSITIVITY == "sensitive":

    EAR_THRESHOLD = 0.25

elif EYE_SENSITIVITY == "low":

    EAR_THRESHOLD = 0.21

else:

    EAR_THRESHOLD = 0.23


print("=" * 60)
print("AI CONFIGURATION")
print(
    "EAR Threshold     :",
    EAR_THRESHOLD
)
print(
    "Drowsiness After  :",
    DROWSINESS_SECONDS,
    "seconds"
)
print(
    "Alarm Enabled     :",
    ALARM_SOUND_ENABLED
)
print(
    "AI Enabled        :",
    AI_DETECTION_ENABLED
)
print("=" * 60)


# ==========================================================
# AI DETECTION CHECK
# ==========================================================

if not AI_DETECTION_ENABLED:

    print("=" * 60)
    print("AI DETECTION IS OFF")
    print("Enable AI Detection from Settings.")
    print("=" * 60)

    raise SystemExit


# ==========================================================
# MYSQL DATABASE
# ==========================================================

try:

    db = pymysql.connect(
        host="localhost",
        user="root",
        password="ROOT@123",
        database="sleep_alarm_pro"
    )

    cursor = db.cursor()

    print("=" * 60)
    print("MYSQL DATABASE CONNECTED")
    print("=" * 60)

except Exception as e:

    print("=" * 60)
    print("MYSQL CONNECTION ERROR")
    print(e)
    print("=" * 60)

    db = None
    cursor = None


# ==========================================================
# SESSION VARIABLES
# ==========================================================

study_start = time.time()

focus_score = 100

drowsiness_count = 0

closed_start_time = None

alarm_played = False

eye_status = "Eyes Open"

head_status = "Looking Forward"


# ==========================================================
# MEDIAPIPE FACE MESH
# ==========================================================

mp_face_mesh = mp.solutions.face_mesh

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)


# ==========================================================
# CAMERA
# ==========================================================

cap = cv2.VideoCapture(0)

if not cap.isOpened():

    print("=" * 60)
    print("ERROR: CAMERA COULD NOT BE OPENED")
    print("=" * 60)

    if db:

        db.close()

    raise SystemExit


print("=" * 60)
print("CAMERA STARTED SUCCESSFULLY")
print("Sleep Alarm Pro AI Detection")
print("Press Q or ESC to stop")
print("=" * 60)


# ==========================================================
# DISTANCE FUNCTION
# ==========================================================

def distance(a, b):

    return math.sqrt(
        (a[0] - b[0]) ** 2 +
        (a[1] - b[1]) ** 2
    )


# ==========================================================
# ALARM FUNCTION
# ==========================================================

def play_alarm():

    try:

        alarm_path = os.path.join(
            os.path.dirname(
                os.path.dirname(__file__)
            ),
            "sounds",
            "alarm.mp3"
        )

        if os.path.exists(alarm_path):

            playsound(alarm_path)

        else:

            print(
                "Alarm file not found:"
            )

            print(
                alarm_path
            )

    except Exception as e:

        print(
            "Alarm Error:",
            e
        )


# ==========================================================
# MAIN CAMERA LOOP
# ==========================================================

try:

    while True:

        success, frame = cap.read()

        if not success:

            print(
                "Could not read camera frame."
            )

            break


        # ==================================================
        # MIRROR CAMERA
        # ==================================================

        frame = cv2.flip(
            frame,
            1
        )


        # ==================================================
        # CONVERT BGR → RGB
        # ==================================================

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )


        # ==================================================
        # FACE DETECTION
        # ==================================================

        results = face_mesh.process(
            rgb
        )


        # Default display color

        color = (
            255,
            255,
            255
        )


        # ==================================================
        # FACE FOUND
        # ==================================================

        if results.multi_face_landmarks:

            face = (
                results.multi_face_landmarks[0]
            )

            h, w, _ = frame.shape


            # ----------------------------------------------
            # LANDMARK FUNCTION
            # ----------------------------------------------

            def pt(landmark_id):

                return (
                    int(
                        face.landmark[
                            landmark_id
                        ].x * w
                    ),

                    int(
                        face.landmark[
                            landmark_id
                        ].y * h
                    )
                )


            # ==================================================
            # LEFT EYE EAR
            # ==================================================

            leftEAR = (

                distance(
                    pt(160),
                    pt(144)
                )

                +

                distance(
                    pt(158),
                    pt(153)
                )

            ) / (

                2 *

                distance(
                    pt(33),
                    pt(133)
                )

            )


            # ==================================================
            # RIGHT EYE EAR
            # ==================================================

            rightEAR = (

                distance(
                    pt(385),
                    pt(380)
                )

                +

                distance(
                    pt(387),
                    pt(373)
                )

            ) / (

                2 *

                distance(
                    pt(362),
                    pt(263)
                )

            )


            # ==================================================
            # AVERAGE EAR
            # ==================================================

            ear = (
                leftEAR +
                rightEAR
            ) / 2


            # ==================================================
            # HEAD DIRECTION
            # ==================================================

            nose = face.landmark[1]

            forehead = face.landmark[10]

            chin = face.landmark[152]

            left_face = face.landmark[234]

            right_face = face.landmark[454]


            nose_x = int(
                nose.x * w
            )

            nose_y = int(
                nose.y * h
            )


            left_x = int(
                left_face.x * w
            )

            right_x = int(
                right_face.x * w
            )


            top_y = int(
                forehead.y * h
            )

            bottom_y = int(
                chin.y * h
            )


            face_center_x = (
                left_x +
                right_x
            ) // 2


            face_center_y = (
                top_y +
                bottom_y
            ) // 2


            dx = (
                nose_x -
                face_center_x
            )


            dy = (
                nose_y -
                face_center_y
            )


            head_status = (
                "Looking Forward"
            )


            if dx < -20:

                head_status = (
                    "Looking Left"
                )

            elif dx > 20:

                head_status = (
                    "Looking Right"
                )

            elif dy < -20:

                head_status = (
                    "Looking Up"
                )

            elif dy > 20:

                head_status = (
                    "Looking Down"
                )


            # ==================================================
            # EYE DETECTION
            # ==================================================

            if ear > EAR_THRESHOLD:

                eye_status = (
                    "Eyes Open"
                )

                color = (
                    0,
                    255,
                    0
                )


                # Reset closed-eye timer

                closed_start_time = None


                # Allow next drowsiness alarm

                alarm_played = False


            else:

                eye_status = (
                    "Eyes Closed"
                )

                color = (
                    0,
                    0,
                    255
                )


                # Start closed-eye timer

                if closed_start_time is None:

                    closed_start_time = (
                        time.time()
                    )


                closed_time = (
                    time.time()
                    -
                    closed_start_time
                )


                # ==================================================
                # CLOSED TIME
                # ==================================================

                cv2.putText(

                    frame,

                    f"Closed Time : {closed_time:.1f}s",

                    (20, 120),

                    cv2.FONT_HERSHEY_SIMPLEX,

                    0.8,

                    (0, 0, 255),

                    2

                )


                # ==================================================
                # DROWSINESS DETECTION
                # ==================================================

                if closed_time >= DROWSINESS_SECONDS:


                    cv2.putText(

                        frame,

                        "DROWSINESS DETECTED",

                        (150, 40),

                        cv2.FONT_HERSHEY_SIMPLEX,

                        0.8,

                        (0, 0, 255),

                        2

                    )


                    # ==================================================
                    # DROWSINESS EVENT
                    # ==================================================

                    if not alarm_played:


                        # ------------------------------------------
                        # ALARM ON
                        # ------------------------------------------

                        if ALARM_SOUND_ENABLED:

                            print(
                                "DROWSINESS DETECTED - ALARM ON"
                            )


                            threading.Thread(

                                target=play_alarm,

                                daemon=True

                            ).start()


                        # ------------------------------------------
                        # ALARM OFF
                        # ------------------------------------------

                        else:

                            print(
                                "DROWSINESS DETECTED - ALARM OFF"
                            )


                        # Mark event as processed

                        alarm_played = True


                        # Increase drowsiness count

                        drowsiness_count += 1


                        # Reduce focus

                        if focus_score > 0:

                            focus_score = max(

                                0,

                                focus_score - 5

                            )


            # ==================================================
            # CAMERA INFORMATION
            # ==================================================

            cv2.putText(

                frame,

                f"EAR : {ear:.2f}",

                (20, 40),

                cv2.FONT_HERSHEY_SIMPLEX,

                1,

                color,

                2

            )


            cv2.putText(

                frame,

                eye_status,

                (20, 80),

                cv2.FONT_HERSHEY_SIMPLEX,

                1,

                color,

                2

            )


            cv2.putText(

                frame,

                head_status,

                (20, 160),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.8,

                (255, 255, 0),

                2

            )


            cv2.putText(

                frame,

                f"Focus Score : {focus_score}%",

                (20, 200),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.8,

                (255, 255, 255),

                2

            )


            cv2.putText(

                frame,

                f"Drowsiness : {drowsiness_count}",

                (20, 240),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.8,

                (255, 255, 255),

                2

            )


            # Show current alarm setting

            alarm_text = (

                "Alarm: ON"
                if ALARM_SOUND_ENABLED
                else
                "Alarm: OFF"
            )


            cv2.putText(

                frame,

                alarm_text,

                (20, 280),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.8,

                (
                    0,
                    255,
                    0
                )
                if ALARM_SOUND_ENABLED
                else
                (
                    0,
                    0,
                    255
                ),

                2

            )


        # ==================================================
        # FACE NOT FOUND
        # ==================================================

        else:

            cv2.putText(

                frame,

                "Face Not Found",

                (20, 40),

                cv2.FONT_HERSHEY_SIMPLEX,

                1,

                (0, 0, 255),

                2

            )


        # ==================================================
        # SHOW CAMERA
        # ==================================================

        cv2.imshow(

            "Sleep Alarm Pro - AI Detection",

            frame

        )


        # ==================================================
        # KEYBOARD CONTROL
        # ==================================================

        key = (
            cv2.waitKey(1)
            &
            0xFF
        )


        # Q / ESC

        if (

            key == ord("q")

            or

            key == ord("Q")

            or

            key == 27

        ):

            print(
                "Closing Camera..."
            )

            break


        # ==================================================
        # WINDOW CLOSE BUTTON
        # ==================================================

        try:

            if cv2.getWindowProperty(

                "Sleep Alarm Pro - AI Detection",

                cv2.WND_PROP_VISIBLE

            ) < 1:

                print(
                    "Camera Window Closed."
                )

                break

        except:

            break


# ==========================================================
# HANDLE ERRORS
# ==========================================================

except Exception as e:

    print("=" * 60)

    print(
        "CAMERA AI ERROR"
    )

    print(e)

    print("=" * 60)


# ==========================================================
# SAVE STUDY SESSION
# ==========================================================

finally:

    study_end = time.time()


    study_minutes = max(

        1,

        int(

            (
                study_end -
                study_start
            )
            /
            60

        )

    )


    print("=" * 60)

    print(
        "STUDY SESSION FINISHED"
    )

    print("=" * 60)


    print(

        f"Study Time       : "
        f"{study_minutes} minute(s)"

    )


    print(

        f"Focus Score      : "
        f"{focus_score}%"

    )


    print(

        f"Drowsiness Count : "
        f"{drowsiness_count}"

    )


    print("=" * 60)


    # ==================================================
    # SAVE TO MYSQL
    # ==================================================

    if cursor and db:

        try:

            sql = """
                INSERT INTO study_sessions
                (
                    user_id,
                    study_time,
                    focus_score,
                    drowsiness_count,
                    session_date
                )
                VALUES (%s, %s, %s, %s, %s)
            """


            values = (

                1,

                study_minutes,

                focus_score,

                drowsiness_count,

                datetime.now()

            )


            cursor.execute(

                sql,

                values

            )


            db.commit()


            print("=" * 60)

            print(
                "STUDY SESSION SAVED TO MYSQL"
            )

            print("=" * 60)


        except Exception as e:

            print("=" * 60)

            print(
                "DATABASE SAVE ERROR"
            )

            print(e)

            print("=" * 60)


            try:

                db.rollback()

            except:

                pass


    # ==================================================
    # CLEANUP
    # ==================================================

    try:

        if cursor:

            cursor.close()

    except:

        pass


    try:

        if db:

            db.close()

    except:

        pass


    try:

        cap.release()

    except:

        pass


    try:

        cv2.destroyAllWindows()

    except:

        pass


    print(
        "Camera released."
    )

    print(
        "AI detection stopped."
    )
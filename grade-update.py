#
# Henry Acevedo
#
# Purpose: To sync process of ALT-instruction with Canvas.
#

import pypyodbc
import time
from datetime import datetime
from canvasapi import Canvas
from canvasapi import exceptions
from configparser import ConfigParser
from collections import defaultdict

config = ConfigParser()
config.read("config.ini")
MYURL = config.get("instance", "prod")
MYTOKEN = config.get("auth", "token")

canvas = Canvas(MYURL, MYTOKEN)


def main():
    # These are queries and corresponding assignment id in Canvas
    assignDict = {
        "ALTSCOAA-Final": 411637,
        "ALTLOWBAND": 411638,
        "ALTLM": 411639,
        "ALT-Gradebook": 411640,
        "ALT-QuizExam": 411641,
        "TPWSTQ": 411642,
        "ALT-TPTAD": 411643,
        "ALTPRESENCE": 411644,
        "TPTFGL": 411645,
        "ALT-RWTR": 421373,
    }

    # Load the course with course id
    alt_course = canvas.get_course(50692)
    not_added = []

    pypyodbc.lowercase = False
    conn = pypyodbc.connect(
        r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        + r"Dbq=..\Database.accdb;"
    )
    cur = conn.cursor()

    # ALT Instruction
    for key, value in tqdm(assignDict.items()):
        # Get list of completers for this query, to load into corresponding assignment
        cur.execute(f"SELECT * FROM [{key}]")

        assignment = alt_course.get_assignment(value)

        while True:
            row = cur.fetchone()
            if row is None:
                break

            # Try to load up the corresponding Canvas user based on query
            try:
                cUser = canvas.get_user(
                    f"{row[0].split('@')[0]}@calstatela.edu", id_type="sis_login_id"
                )
                # Enroll them into the course without invitation.
                # Enrolling if they are already there doesn't do anything.
                alt_course.enroll_user(
                    cUser.id,
                    "StudentEnrollment",
                    enrollment={"enrollment_state": "active"},
                )

                # Grab the submission object, and check if they are already graded
                sub = assignment.get_submission(cUser.id)
                if sub.entered_score == 1.0:
                    continue

                # If they haven't been graded, change the score.
                sub.edit(submission={"posted_grade": "pass"})

            except exceptions.ResourceDoesNotExist as e:
                not_added.append(row[0])

    cur.close()
    conn.close()

    not_added = set(not_added)
    if len(not_added) > 8:
        print(not_added)


if __name__ == "__main__":
    main()

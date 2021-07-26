#
# Henry Acevedo
#
# Purpose: To sync assignment completion with Database.
#

import pypyodbc
from datetime import datetime
from tabulate import tabulate
from canvasapi import Canvas
from canvasapi import exceptions
from configparser import ConfigParser
from collections import defaultdict
import win32com.client as win32

config = ConfigParser()
config.read("config.ini")
MYURL = config.get("instance", "prod")
MYTOKEN = config.get("auth", "token")

canvas = Canvas(MYURL, MYTOKEN)


def main():
    emailLookup = {}
    course_lookup = {}
    assignment_lookup = {}
    pypyodbc.lowercase = False
    conn = pypyodbc.connect(
        r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        + r"Dbq=..\CETL Database.accdb;"
    )
    cur = conn.cursor()

    # Get data from course lookup
    cur.execute("SELECT * FROM [Canvas_course_lookup]")

    while True:
        row = cur.fetchone()
        if row is None:
            break
        course_lookup[row[0]] = [row[1], row[2]]

    print(course_lookup)

    # Get data from course assignment lookup
    cur.execute("SELECT * FROM [canvas_assignment_lookup]")

    while True:
        row = cur.fetchone()
        if row is None:
            break
        assignment_lookup[row[0]] = [row[1], row[2], row[3]]

    print(assignment_lookup)

    sql_command = (
        "INSERT INTO [Faculty-Program] "
        "(FEmail, FProgram, Attended, DateTaken) VALUES (?, ?, ?, ?)"
    )

    added = []
    existing = []

    # Generic course completion checking. This uses the Canvas grading scheme and the word "Complete".
    for key, value in course_lookup.items():
        course = canvas.get_course(key)
        # print(course)
        enrollments = course.get_enrollments(type=["StudentEnrollment"])
        for enroll in enrollments:
            if enroll.grades["final_grade"] == "Complete":
                email = enroll.user["login_id"].lower()

                start = datetime.strptime(
                    enroll.last_activity_at.split("T")[0].lower(), "%Y-%m-%d"
                )

                params = (
                    email,
                    value[1],
                    "Complete",
                    start.strftime("%m/%d/%Y"),
                )

                # Try to insert record, if fail because of integrity constraint ignore.
                try:
                    cur.execute(sql_command, params)
                    added.append((enroll.user["name"], email, value[1]))
                except pypyodbc.Error as ex:
                    sqlstate = ex.args[0]
                    if sqlstate == "23000":
                        existing.append((enroll.user["name"], email, value[1]))
                    else:
                        print(sqlstate, ex)
                conn.commit()

    # Generic assignment completion checking.
    for key, value in assignment_lookup.items():
        course = canvas.get_course(key)
        # print(course)
        c_assign = course.get_assignment(value[0])
        submissions = c_assign.get_submissions(include=["user"])
        for sub in submissions:
            if sub.score is not None and sub.score >= value[1]:
                email = emailLookup.get(
                    sub.user["login_id"].lower(), sub.user["login_id"].lower()
                )
                start = datetime.strptime(sub.graded_at.split("T")[0], "%Y-%m-%d")

                params = (email, value[2], "Complete", start.strftime("%m/%d/%Y"))

                try:
                    cur.execute(sql_command, params)
                    added.append((sub.user["name"], email, value[2]))
                except pypyodbc.Error as ex:
                    sqlstate = ex.args[0]
                    if sqlstate == "23000":
                        existing.append((sub.user["name"], email, value[2]))
                    else:
                        print(sqlstate, ex)
                conn.commit()

    cur.close()
    conn.close()

    addedTable = tabulate(added, tablefmt="html", headers=["name", "email", "program"])
    notTable = tabulate(existing, tablefmt="html", headers=["name", "email", "program"])

    if added != []:
        print(addedTable, notTable)


if __name__ == "__main__":
    main()

# Henry Acevedo
# Eventbrite - pulling data for Database
#

import pypyodbc
import datetime
from tabulate import tabulate
from eventbrite import Eventbrite
from configparser import ConfigParser
import win32com.client as win32

config = ConfigParser()
config.read("config.ini")
MYTOKEN = config.get("auth", "event")

eventbrite = Eventbrite(MYTOKEN)


# This is used as a transction report so that other people are able to see if people are loaded succesfully.
def sendEmail(sum_data, aTable, eTable, nTable):
    outlook = win32.Dispatch("outlook.application")
    mail = outlook.CreateItem(0)
    mail.To = 'others@email.com'
    mail.CC = "me@email.com"
    mail.Subject = "Database Sync Report"
    mail.HTMLBody = f"""<h2><p>Summary: <span style="color:green">{sum_data[0]}</span> / <span style="color:gray">{sum_data[1]}</span> / <span style="color:red">{sum_data[2]}</span></p></h2><br>
                    The following people were added to the database:
                    <br>{aTable}<br><br>
                    The following people were not added because
                     they already existed:
                    <br>{eTable}<br><br>
                    The following people were not added because no
                     matching program was found
                    <br>{nTable}<br><br>"""
    mail.Send()


def write_info(peopleEvents, attendees):
    event_dict = {}
    for attendee in attendees["attendees"]:
        if attendee["event_id"] not in event_dict:
            event = eventbrite.get_event(attendee["event_id"])
            eventName = event["name"]["text"].lower()
            eventName = " ".join(eventName.split())
            startd = datetime.datetime.strptime(
                event["start"]["local"], "%Y-%m-%dT%H:%M:%S"
            )
            event_dict[event.id] = {
                "name": eventName,
                "start": startd.strftime("%m/%d/%Y %I:%M %p")
            }
        if attendee["checked_in"]:
            try:
                peopleEvents.append(
                    (
                        attendee["profile"].get("name", "None"),
                        attendee["profile"].get("email", "None"),
                        event_dict[attendee["event_id"]]['name'],
                        attendee["answers"][0].get("answer", "No Answer"),
                        attendee["answers"][1].get("answer", "No Answer"),
                        event_dict[attendee["event_id"]]['start']
                    )
                )
            except IndexError as e:
                peopleEvents.append(
                    (
                        attendee["profile"].get("name", "None"),
                        attendee["profile"].get("email", "None"),
                        event_dict[attendee["event_id"]]['name'],
                        "No Question",
                        "No Question",
                        event_dict[attendee["event_id"]]['start']
                    )
                )

    return peopleEvents


def main():
    # Get time x time ago
    dt = datetime.datetime.now() - datetime.timedelta(days=7)
    # YYYY-MM-DDThh:mm:ssZ
    dt = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    eventLookup = {}
    emailLookup = {}
    pypyodbc.lowercase = False
    conn = pypyodbc.connect(
        r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        + r"Dbq=..\Database.accdb;"
    )
    cur = conn.cursor()

    # Get data from event lookup, this table in the database associates
    # event names with DB program codes.
    cur.execute("SELECT * FROM [Event-Lookup]")

    while True:
        row = cur.fetchone()
        if row is None:
            break
        eventName = row[0].lower()
        eventName = " ".join(eventName.split())
        eventLookup[eventName] = row[1]

    user = eventbrite.get_user()
    peopleEvents = []

    # Start pulling data from Evenbtbrite
    payload = {"changed_since": dt}
    attendees = eventbrite.get(f"/organizations/xxxxxxxxxxx/attendees/", data=payload)

    peopleEvents = write_info(peopleEvents, attendees)

    while attendees["pagination"]["has_more_items"]:
        payload['continuation'] = attendees["pagination"]["continuation"]
        attendees = eventbrite.get(f"/organizations/xxxxxxxxxx/attendees/", data=payload)
        peopleEvents = write_info(peopleEvents, attendees)

    sql_command = (
        "INSERT INTO [Faculty-Program] "
        "(FEmail, FProgram, Attended, DateTaken) VALUES (?, ?, ?, ?)"
    )

    existing = []
    added = []
    notAdded = []
    for entry in peopleEvents:
        email = entry[1].lower()

        # Try to find the event in the datbase, if it doesn't exist put it in list.
        if entry[2] not in eventLookup or eventLookup[entry[2]] is None:
            notAdded.append((entry[0], email, entry[2], entry[3], entry[4]))
        else:
            params = (email, eventLookup[entry[2]], "Complete", entry[5])

            # Try adding person-program to database, if they already exist catch the error and list.
            try:
                cur.execute(sql_command, params)
                added.append(
                    (entry[0], email, eventLookup[entry[2]], entry[3], entry[4])
                )
            except pypyodbc.Error as ex:
                sqlstate = ex.args[0]
                if sqlstate == "23000":
                    existing.append(
                        (entry[0], email, eventLookup[entry[2]], entry[3], entry[4])
                    )
                else:
                    print(sqlstate, ex)
            conn.commit()

    # Format lists for transaction report email.
    addedTable = tabulate(
        added,
        tablefmt="html",
        headers=["name", "email", "program", "status", "department"],
    )
    existingTable = tabulate(
        existing,
        tablefmt="html",
        headers=["name", "email", "program", "status", "department"],
    )
    notTable = tabulate(
        notAdded,
        tablefmt="html",
        headers=["name", "email", "program", "status", "department"],
    )

    sum_data = [len(added), len(existing), len(notAdded)]

    print(addedTable, existingTable, notTable)
    sendEmail(sum_data, addedTable, existingTable, notTable)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

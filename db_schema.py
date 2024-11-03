from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash

db = SQLAlchemy()

#ALL variable and class names are SINGULAR. Only class names are capitalised.
#Registered users
class User(db.Model, UserMixin):
    #This must be named id
    id = db.Column(db.Integer, primary_key=True, autoincrement = True)  #unique
    email = db.Column(db.String(), unique = True, nullable = False)  #unique
    passwordHash = db.Column(db.String(), unique = False, nullable = False)
    isOrganiser = db.Column(db.Boolean, unique = False, nullable = False, default = False)
    ticket = db.relationship("Ticket", backref = "user", lazy = True)
    #Unread messages
    attendeeUnread = db.Column(db.Integer, unique = False, nullable = True)
    organiserUnread = db.Column(db.Integer, unique = False, nullable = True)

    def __init__(self, email, passwordHash, isOrganiser):  
        self.email = email
        self.passwordHash = passwordHash
        self.isOrganiser = isOrganiser
        self.attendeeUnread = 0
        self.organiserUnread = 0

#Available events
class Event(db.Model):
    eventId = db.Column(db.Integer, primary_key=True, autoincrement = True)  #unique
    name = db.Column(db.String(), unique = True, nullable = False)  #unique
    date = db.Column(db.String(), unique = False, nullable = False)
    time = db.Column(db.String(), unique = False, nullable = False)
    duration = db.Column(db.String(), unique = False, nullable = False)
    capacity = db.Column(db.Integer, unique = False, nullable = False)
    location = db.Column(db.String(), unique = False, nullable = False)
    remaining = db.Column(db.Integer, unique = False, nullable = False)  #Number of spaces remaining
    almostFull = db.Column(db.Boolean, unique = False, nullable = False)  #remaining / capacity less than 5%
    full = db.Column(db.Boolean, unique = False, nullable = False)  #remaining = 0

    def __init__(self, name, date, time, duration, capacity, location):  
        self.name = name
        self.date = date
        self.time = time
        self.duration = duration
        self.capacity = int(capacity)
        self.location = location
        self.remaining = capacity
        self.almostFull = False
        self.full = False

#Valid tickets: One user can have many tickets.
class Ticket(db.Model):
    ticketId = db.Column(db.Integer, primary_key=True, autoincrement = True)  #unique
    userId = db.Column(db.Integer, db.ForeignKey("user.id"))  #foreign key -> backref
    eventId = db.Column(db.Integer, unique = False, nullable = False)
    #The following variables are properties of the event.
    name = db.Column(db.String(), unique = False, nullable = False)  #unique
    date = db.Column(db.String(), unique = False, nullable = False)
    time = db.Column(db.String(), unique = False, nullable = False)
    duration = db.Column(db.String(), unique = False, nullable = False)
    location = db.Column(db.String(), unique = False, nullable = False)
    valid = db.Column(db.Boolean, unique = False, nullable = False)

    def __init__(self, userId, eventId, name, date, time, duration, location):  
        self.userId = userId
        self.eventId = eventId
        self.name = name
        self.date = date
        self.time = time
        self.duration = duration
        self.location = location
        self.valid = True

#Messages sent by organisers
class Message(db.Model):
    messageId = db.Column(db.Integer, primary_key=True, autoincrement = True)  #unique
    title = db.Column(db.String(), unique = False, nullable = True) 
    recipient = db.Column(db.Integer, unique = False, nullable = False)    #0 for all users, -1 for all organisers only, others = user ID
    date = db.Column(db.String(), unique = False, nullable = True) 
    time = db.Column(db.String(), unique = False, nullable = True) 
    content = db.Column(db.String(), unique = False, nullable = True) 
 
    def __init__(self, title, recipient, date, time, content):
        self.title = title
        self.recipient = recipient
        self.date = date
        self.time = time
        self.content = content


def dbinit():

    db.session.commit()


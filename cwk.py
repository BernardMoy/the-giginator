from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from markupsafe import escape

from flask import Flask, render_template, request, redirect, url_for
app = Flask(__name__)
app.secret_key = 'ASecretKey0302'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/login"    #default route if not logged in

@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id = user_id).first()


app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///todo.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from db_schema import db, User, Ticket, Event, Message, dbinit

db.init_app(app)

resetdb = True
if resetdb:
    with app.app_context():
        db.drop_all()
        db.create_all()
        dbinit()

#Percentage of remaining spaces of an event where the last X spaces will be shown, and organisers will be notified.
criticalPercentage = 5

criticalPercentage = criticalPercentage/100


#app routes

@app.route('/') #home
def home():
    allEvent = Event.query.all()
    return render_template('home.html', allEvent = allEvent)

@app.route('/index')
@login_required
def index():
    allEvent = Event.query.all()
    return render_template('index.html', allEvent = allEvent)


#login -> loginAuthentication -> index
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/loginAuthentication', methods = ['POST'])
def loginAuthentication():
    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        safeEmail = escape(email)

        #User does not exist.
        user = User.query.filter_by(email = safeEmail).first()
        userNotExist = user is None
        if userNotExist:
            return render_template('login.html', warning = "Couldn't find a user with that email. Perhaps you haven't registered?")
        
        #Password incorrect, provided user exist.
        dbPasswordHash = user.passwordHash
        if not check_password_hash(dbPasswordHash, password):
            return render_template('login.html', warning = "The password entered was incorrect.")

    login_user(user)
    return redirect ('/index')



#register -> registerAuthentication -> index
@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/registerAuthentication', methods = ['POST'])
def registerAuthentication():
    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        safeEmail = escape(email)
        passwordHash = generate_password_hash(password)

        #User with the same email already exist.
        userExist = User.query.filter_by(email = safeEmail).first()
        if userExist is not None:
            return render_template('register.html', warning = "An user with this email address is already registered. Please login.")

        #Create a new user, then add it to the database
        newUser = User(safeEmail, passwordHash, False)
        db.session.add(newUser)
        db.session.commit()

    login_user(newUser)
    return redirect('/index')


@app.route('/profile')
@login_required
def profile():
    #When redirected to this page, reset the number of attendee unread to 0
    current_user.attendeeUnread = 0
    db.session.commit()

    #Get message that is either send to all attendees, or the target current user
    allMessage = Message.query.filter(or_(Message.recipient == 0, Message.recipient == current_user.id)).order_by(Message.messageId.desc()).all()
    messageNumber = len(allMessage)
    return render_template('profile.html', allMessage = allMessage, messageNumber = messageNumber)

@app.route('/ticket')
@login_required
def ticket():
    allTicket = Ticket.query.filter_by(userId = current_user.id).filter_by(valid = True).order_by(Ticket.ticketId.desc()).all()
    return render_template('ticket.html', allTicket = allTicket)

@app.route('/ticketBarcode')
@login_required
def ticketBarcode():
    ticketId = request.args.get('ticketId')
    ticket = Ticket.query.filter_by(ticketId = ticketId).filter_by(valid = True).first()

    #The current user is not the owner of the ticker
    ticketUser = ticket.userId
    if ticketUser != current_user.id:
        return redirect('/login')


    return render_template('ticketBarcode.html', entry = ticket)


@app.route('/event')
@login_required
def event():
    eventId = request.args.get('id')   #Get the event id from query string
    event = Event.query.filter_by(eventId = eventId).first()
    ticket = Ticket.query.filter_by(userId = current_user.id).filter_by(eventId = eventId).filter_by(valid = True).first()
    haveTicket = ticket is not None

    #If the user already have a ticket
    if haveTicket:

        ticketId = ticket.ticketId

        return redirect(url_for('ticketBarcode', ticketId = ticketId, eventId = eventId))

    #If the event is full
    if event.full:
        return render_template('event.html', entry = event, route = "/index", method = "", buttonName = "Full! Come back later for a")

    #If the user don't already have a ticket
    else:        
        return render_template('event.html', entry = event, route = "/createTicket", method = "POST", buttonName = "Get")


#User creates a new ticket
@app.route('/createTicket', methods = ['POST'])
@login_required
def createTicket():
    if request.method == 'POST':
        userId = current_user.id
        eventId = request.form.get("eventId")

        #If the user already have a valid ticket
        haveTicket = Ticket.query.filter_by(userId = userId).filter_by(eventId = eventId).filter_by(valid = True).first() is not None
        if haveTicket:
            return redirect('/ticket')
        

        #If the user don't already have a ticket:
        #Get the properties of the event, then create a ticket (so that we can refer to the event properties in the ticket.)
        event = Event.query.filter_by(eventId = eventId).first()

        name = event.name
        date = event.date
        time = event.time
        duration = event.duration
        location = event.location

        #If a ticket is created, decrease its remaining by 1.
        event.remaining -= 1

        #If remaining space <5%, then change the almostFull property to true and message organisers.
        if event.remaining / event.capacity < criticalPercentage:
            event.almostFull = True

            newMessage = Message("[System] An event is getting full", -1, "-", "-", "The event " + str(event.name) + " has fewer than 5% of spaces remaining.")
            
            allOrganiser = User.query.filter_by(isOrganiser = True).all()
            for user in allOrganiser:
                user.organiserUnread += 1
            db.session.commit()

            db.session.add(newMessage)

        else:
            event.almostFull = False

        #If remaining space = 0, then change the full property to true.
        if event.remaining == 0:
            event.full = True
        else:
            event.full = False

        newTicket = Ticket(userId, eventId, name, date, time, duration, location)
        db.session.add(newTicket)

        db.session.commit()

        return redirect('/ticket')


@app.route('/deleteTicket', methods = ['GET'])
@login_required
def deleteTicket():
    if request.method == "GET":
        eventId = request.args.get("eventId")
        userId = current_user.id

        ticket = Ticket.query.filter_by(userId = userId).filter_by(eventId = eventId).filter_by(valid = True).first()
        ticket.valid = False

        #If a ticket is deleted, increase its remaining by 1.
        event = Event.query.filter_by(eventId = eventId).first()
        event.remaining += 1

        #If remaining space <5%, then change the almostFull property to true and message organisers.
        if event.remaining / event.capacity < criticalPercentage:
            event.almostFull = True
        else:
            event.almostFull = False
        
        #If remaining space = 0, then change the full property to true.
        if event.remaining == 0:
            event.full = True
        else:
            event.full = False


        db.session.commit()

        return redirect('/ticket')

#Organiser routes
#OrganiserLogin -> OrganiserAuthentication -> (check if the user is organiser)  index
@app.route('/organiserLogin')
def organiserLogin():
    return render_template('organiserLogin.html')

@app.route('/organiserAuthentication', methods = ['POST'])
def organiserAuthentication():
    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        safeEmail = escape(email)

        #User does not exist.
        user = User.query.filter_by(email = safeEmail).first()
        userNotExist = user is None
        if userNotExist:
            return render_template('organiserLogin.html', warning = "Couldn't find a user with that email. Perhaps you haven't registered?")
        
        #The user is not an organiser.
        if user.isOrganiser == False:
            return render_template('organiserLogin.html', warning = "This user is not an organiser. If you are new, please register by clicking the link below.")
        
        #Password incorrect, provided user exist and is organiser.
        dbPasswordHash = user.passwordHash
        if not check_password_hash(dbPasswordHash, password):
            return render_template('organiserLogin.html', warning = "The password entered was incorrect.")
        
    login_user(user)
    return redirect('/organiserIndex')

#OrganiserRegister ->  organiserRegisterAuthentication(check if the user is organiser) index
#Authentication required to prevent changing url.
@app.route('/organiserRegister')
def organiserRegister():
    return render_template('organiserRegister.html')

@app.route('/organiserRegisterAuthentication', methods = ['POST'])
def organiserRegisterAuthentication():
    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        safeEmail = escape(email)

        user = User.query.filter_by(email = safeEmail).first()
        #The user does not exist.
        if user is None:
            return render_template('register.html', warning = "This user does not exist. Please register as an attendee first.")
        
        #User with the same email already exist, and is an organiser. --> Please login.
        if user.isOrganiser == True:
            return render_template('organiserLogin.html', warning = "An organiser user with this email address is already registered. Please login.")
                
        dbPasswordHash = user.passwordHash
        #User with the same email already exist, but is NOT an organiser. But the user details are incorrect.
        if not check_password_hash(dbPasswordHash, password):
            return render_template('organiserRegister.html', warning = "The username, password or code entered was incorrect.")

    #The user exist, is not an organiser, and details are correct. --> Promote to an organiser (Since they already provided the correct code.)
    user.isOrganiser = True
    db.session.commit()

    login_user(user)
    return redirect('/organiserIndex')

#Organiser routes: We will need to check if the current user is organiser.
@app.route('/organiserIndex')
@login_required
def organiserIndex():
    #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")
    
    return render_template('organiserIndex.html')


@app.route('/organiserManageEvent')
@login_required
def organiserManageEvent():
    #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")
    
    #retrieve any warnings from query string.
    warning = request.args.get('warning')
    if warning is None:
        warning = ""

    allEvent = Event.query.all()
    return render_template('organiserManageEvent.html', allEvent = allEvent, warning = warning)


@app.route('/createEvent', methods = ['POST'])
@login_required
def createEvent():
    #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")
    
    if request.method == 'POST':
        name = request.form.get("name")
        date = request.form.get("date")
        time = request.form.get("time")
        duration = request.form.get("duration")
        capacity = request.form.get("capacity")
        location = request.form.get("location")

        safeName = escape(name)
        safeDate = escape(date)
        safeTime = escape(time)
        safeDuration = escape(duration)
        safeCapacity = escape(capacity)
        safeLocation = escape(location)

        newEvent = Event(safeName, safeDate, safeTime, safeDuration, safeCapacity, safeLocation)
        db.session.add(newEvent)
        db.session.commit()

        allEvent = Event.query.all()
        return redirect('/organiserManageEvent')


@app.route('/organiserEvent')
@login_required
def organiserEvent():
     #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")
    
    #retrieve any warnings from query string.
    warning = request.args.get('warning')

    eventId = request.args.get('id')   #Get the event id from query string
    event = Event.query.filter_by(eventId = eventId).first()
    return render_template('organiserEvent.html', entry = event, warning = warning)


#Deleting items is a GET request.
@app.route('/deleteEvent', methods = ['GET'])
@login_required
def deleteEvent():
    #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")
    
    if request.method == 'GET':
        password = request.args.get("password")
        dbPasswordHash = current_user.passwordHash
        
        #Incorrect password.
        if not check_password_hash(dbPasswordHash, password):
            return redirect(url_for('organiserManageEvent', warning = "We couldn't verify your identity. Please try again."))
        
        #Correct password
        else:
            #Delete the event
            eventId = request.args.get('id')
            event = Event.query.filter_by(eventId = eventId).first()
            db.session.delete(event)
            db.session.commit()

            #Make all tickets of the event invalid
            ticket = Ticket.query.filter_by(eventId = eventId).all()
            for item in ticket:
                item.valid = False
            db.session.commit()

            #Message attendees
            newMessage = Message("[System] An event was deleted", 0, "-", "-", "The event " + str(event.name) + " was deleted by an organiser. All tickets of this event has been removed.")
            db.session.add(newMessage)

            allAttendee = User.query.all()
            for user in allAttendee:
                user.attendeeUnread += 1

            db.session.commit()

            return redirect(url_for('organiserManageEvent', warning = "Event deleted!"))      



@app.route('/organiserManageUser')
@login_required
def organiserManageUser():
    #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")
    
    allOrganiser = User.query.filter_by(isOrganiser = True).order_by(User.id.desc()).all()
    allAttendee = User.query.order_by(User.id.desc()).all()

    warning = request.args.get("warning")
    if warning is None:
        warning = ""

    return render_template('organiserManageUser.html', allOrganiser = allOrganiser, allAttendee = allAttendee, warning = warning)


@app.route('/organiserMessage')
@login_required
def organiserMessage():
    #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")
    
    #When redirected to this page, reset the number of attendee unread to 0
    current_user.organiserUnread = 0
    db.session.commit()

    #Message shown in a desending order
    allOrgMessage = Message.query.filter_by(recipient = -1).order_by(Message.messageId.desc()).all()
    organiserMessageNumber = len(allOrgMessage)

    allMessage = Message.query.filter_by(recipient = 0).order_by(Message.messageId.desc()).all()
    messageNumber = len(allMessage)

    #pass all users
    allUser = User.query.all()

    return render_template('organiserMessage.html', allOrgMessage = allOrgMessage, organiserMessageNumber = organiserMessageNumber, allMessage = allMessage, messageNumber = messageNumber, allUser = allUser)

@app.route('/sendMessage', methods = ['POST'])
@login_required
def sendMessage():
    #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")
    
    if request.method == 'POST':
        title = request.form.get("title")
        recipient = request.form.get("recipient")
        date = request.form.get("date")
        time = request.form.get("time")
        content = request.form.get("content")

        #Notify all attendees and organisers
        if int(recipient) == 0:
            allAttendee = User.query.all()
            for user in allAttendee:
                user.attendeeUnread += 1
            db.session.commit()

        elif int(recipient) == -1:
            allOrganiser = User.query.filter_by(isOrganiser = True).all()
            for user in allOrganiser:
                user.organiserUnread += 1
            db.session.commit()
        
        #The message is sent to only a specific user.
        else:
            user = User.query.filter_by(id = recipient).first()
            user.attendeeUnread += 1
            db.session.commit()
            
        safeTitle = escape(title)
        safeDate = escape(date)
        safeTime = escape(time)
        safeContent = escape(content)

        newMessage = Message(safeTitle, recipient, safeDate, safeTime, safeContent)
        db.session.add(newMessage)
        db.session.commit()

    return redirect(url_for('organiserMessage', success = "Message sent!"))

#Each user
@app.route('/organiserUser')
@login_required
def organiserUser():
    #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")
    
    id = request.args.get("id")
    user = User.query.filter_by(id = id).first()

    promoteButton = ""
    #Show the promote user button
    if user.isOrganiser == False:
        promoteButton = """
        <div id = "reVerify">
            <button class = "smallDarkButton secondRow" onclick="reVerify()"> Promote user to organiser</button>             
        </div>
        """
    return render_template("organiserUser.html", entry = user, promoteButton = promoteButton)

@app.route('/promoteUser', methods = ['GET'])
@login_required
def promoteUser():
    #The user is not an organiser.
    if current_user.isOrganiser == False:
        logout_user()
        return render_template('organiserLogin.html', warning = "We couldn't verify your identity. Please login again.")

    #Incorrect password.
    password = request.args.get("password")
    if not check_password_hash(current_user.passwordHash, password):
        return redirect(url_for('organiserManageUser', warning = "We couldn't verify your identity. Please try again."))
    
    #Everything correct -> Promote
    id = request.args.get("id")
    user = User.query.filter_by(id = id).first()
    user.isOrganiser = True
    db.session.commit()
    return redirect(url_for('organiserManageUser', warning = "User promoted to organiser!"))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')



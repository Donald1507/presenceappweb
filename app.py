import numpy as np
import os
from flask_bootstrap import Bootstrap

#Flask content
from flask import Flask, render_template, redirect, Response, url_for, request, session
from flask_login import UserMixin, LoginManager, current_user, login_manager, login_user, logout_user, login_required
from flask_admin.contrib.sqla import ModelView

#Flask Administration module
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_wtf import FlaskForm 
from wtforms.fields.core import Label
from wtforms.validators import InputRequired, Email, Length
from wtforms import StringField, PasswordField, BooleanField, DateField


#Database module 
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref

#Secure password module
from werkzeug.security import generate_password_hash, check_password_hash

#Module for getting ip address
from requests import get

#Module for face recognition
import cv2
from PIL import Image

import datetime
import time


app = Flask(__name__)

bootstrap = Bootstrap(app)

#Database management
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///simplon.db'
app.config['SECRET_KEY'] = 'mysecret'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

db = SQLAlchemy(app)

path = 'users'
faceCascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
recognizer = cv2.face.LBPHFaceRecognizer_create()
font = cv2.FONT_HERSHEY_SIMPLEX


#training of the face recognition model
def getImagesAndLabels(path):
    imagePaths = [os.path.join(path,f) for f in os.listdir(path)]     
    faceSamples=[]
    ids = []
    for imagePath in imagePaths:
        PIL_img = Image.open(imagePath).convert('L') # grayscale
        img_numpy = np.array(PIL_img,'uint8')
        id = int(os.path.split(imagePath)[-1].split(".")[1])
        faces = faceCascade.detectMultiScale(img_numpy)
        for (x,y,w,h) in faces:
            faceSamples.append(img_numpy[y:y+h,x:x+w])
            ids.append(id)
    return faceSamples,ids  

faces,ids = getImagesAndLabels(path)
recognizer.train(faces, np.array(ids))
# Save the model into trainer/trainer.yml
recognizer.write('trainer/trainer.yml')
    
    
login_manager = LoginManager(app)

@login_manager.user_loader
def load_user(user_id):
    return Apprenant.query.get(user_id)

"""
MANAGEMENT OF THE DATABASE TABLES
"""
#table of students
class Apprenant(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    lastName = db.Column(db.String(50))
    firstNames = db.Column(db.String(200))
    birthDate = db.Column(db.Date)
    nationality = db.Column(db.String(100))
    password =  db.Column(db.Unicode(255), nullable=True)
    records = db.relationship('Registre', backref='apprenant')
    
    def __repr__(self):
        return '<%r %r>' % (self.lastName, self.firstNames)

#table of admins    
class Administrateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    lastName = db.Column(db.String(50))
    firstNames = db.Column(db.String(200))
    birthDate = db.Column(db.Date)
    nationality = db.Column(db.String(100))
    password =  db.Column(db.Unicode(255), nullable=True)

#table of signing
class Registre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date)
    startTime = db.Column(db.String(25), nullable=True)
    endTime = db.Column(db.String(25), nullable=True)
    apprenant_id = db.Column(db.Integer, db.ForeignKey('apprenant.id'))

class MyModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Length(min=2)])
    password = PasswordField('Mot de passe', validators=[InputRequired(), Length(min=2)])

#Admin View
admin = Admin(app)

admin.add_view(ModelView(Apprenant, db.session))
admin.add_view(ModelView(Administrateur, db.session))
admin.add_view(ModelView(Registre, db.session))


#Home page of the application
@app.route('/')
def home():
    return render_template('index.html')    
       


       
"""
MANAGEMENT OF THE REGISTRATION PAGE
"""    
#function for taking photos after registering for the future model training                            
def photo_register(faceId):
    
    camera = cv2.VideoCapture(0)
    count = 0
    
    while True:
        success,frame = camera.read() 
           
        gray =  cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = faceCascade.detectMultiScale(
            gray,
            scaleFactor = 1.2,
            minNeighbors = 5,
            minSize = (60,60)
        )
        
        
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x,y), (x + w, y + h), (255, 0, 0), 2)
            count += 1 
            
            cv2.imwrite("users/User." + str(faceId) + '.' + str(count) + '.jpg', gray[y:y+h,x:x+w])

        
        ret,buffer=cv2.imencode('.jpg',frame)
        frame=buffer.tobytes()
        
        yield(b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

#route to manage the video from the register page          
@app.route('/register_video/<int:userId>', methods=['GET'])
def register_video(userId):
    return Response(photo_register(userId), mimetype='multipart/x-mixed-replace; boundary=frame')

#Access to the register page
@app.route('/register', methods = ['GET', 'POST'])
def register():
    
    if request.method == 'GET':
        return render_template('register.html')
    
    elif request.method == 'POST':
    
        email = request.form['e_mail']
        password = request.form['password']
        checkPassword = request.form['checkPassword']
        
        if password != checkPassword:
            message = "Les mots de passe ne correspondent pas. Veuillez réessayer!"
            return render_template('register.html', message=message)
            
        else:
            user = Apprenant.query.filter_by(email=email).first()
            if user:
                hashedPassword = generate_password_hash(password, method='sha256')
                user.password = hashedPassword
                db.session.commit()         
                return render_template('register.html', message="", userId = user.id)
            
            else:
                user = Administrateur.query.filter_by(email=email).first()
                if user:
                    hashedPassword = generate_password_hash(password, method='sha256')
                    user.password = hashedPassword
                    db.session.commit()
                    return redirect('/login')
                else:
                    message = "Vous n'êtes pas dans la base de données de Simplon."
                    return render_template('register.html', message=message)



       
"""
MANAGEMENT OF THE LOGIN PAGE
"""
#function of face recognition 
def faceRecognition(faceId):
    
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    recognizer.read('trainer/trainer.yml')
    
    faceId = int(faceId)
    
    names = [None,'Donald', 'Sara', 'Anne']
    
    while True:
        ret, frame =camera.read()
        gray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        
        faces = faceCascade.detectMultiScale(gray, scaleFactor = 1.2, minNeighbors = 5, minSize = (60,60),)
        for(x,y,w,h) in faces:
            cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)
            id, confidence = recognizer.predict(gray[y:y+h,x:x+w])
            
            # If confidence is less them 100 ==> "0" : perfect match 
            if (35 < confidence < 100):
                username = names[id]
                confidence = round(100 - confidence)
                confidence_percentage = "  {0}%".format(confidence)
                if id == faceId:
                    print(id, '-', confidence)
                    if confidence == 62:
                        camera.release()
                        cv2.destroyAllWindows()
                        redirect('/profile')
                    else:
                        pass
                else:
                    pass
                
            else:
                username = "unknown"
                confidence = round(100 - confidence)
                confidence_percentage = "  {0}%".format(confidence)
            
            cv2.putText(frame, str(username), (x+5,y-5), font, 1, (255,255,255), 2)
            cv2.putText(frame, str(confidence_percentage), (x+5,y+h-5), font, 1, (255,255,0), 1)      
               
        ret,buffer=cv2.imencode('.jpg',frame)
        frame=buffer.tobytes()
        
        yield(b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

#route to manage the video from the login page                
@app.route('/login_video/<int:userId>', methods=['GET'])
def login_video(userId): 
    return Response(faceRecognition(userId), mimetype='multipart/x-mixed-replace; boundary=frame')

#Access to the login page
@app.route('/login', methods = ['GET', 'POST'])
def login():
    
    form = LoginForm()
    
    # Wifi Simplon : '105.235.111.211'
    # Ma MTN pocket: '196.181.137.217'
    ip = get('https://api.ipify.org').text
    
    if ip != '196.180.213.240':
        message = "Veuillez vous connecter au Wifi de la fabrique."
        return render_template('index.html', message=message)

    else:
        if request.method == 'GET':
            return render_template('login.html', form=form)
        
        elif request.method == 'POST':
  
            if form.validate_on_submit():
                user_1 = Apprenant.query.filter_by(email=form.email.data).first()
                user_2 = Administrateur.query.filter_by(email=form.email.data).first()
                
                if not user_1 and not user_2:
                    message = "L'email est incorrect."
                    return render_template('login.html', message=message, form=form)
                
                else: 
                    if user_1:
                        if check_password_hash(user_1.password, form.password.data):
                            return render_template('login.html', message="", userId=user_1.id)
                        else:
                            message = "Le mot de passe est incorrect."
                            return render_template('login.html',form=form, message=message)
                        
                    else:
                        if user_2:
                            if check_password_hash(user_2.password, form.password.data):
                                return redirect('/admin')
                            
                            else:
                                message = "Le mot de passe est incorrect."
                                return render_template('login.html', form=form, message=message)




"""
MANAGEMENT OF THE PROFILE PAGE
"""                 
#Access to the student profile     
@app.route('/profile/<int:userId>', methods=['GET', 'POST'])
def profile(userId):
    
    today = datetime.date.today()
    user = Apprenant.query.filter_by(id=userId).first()
    
    if request.method == 'GET':
        return render_template('profile.html', lastname = user.lastName, firstnames = user.firstNames, userId=userId)
    
    elif request.method == 'POST':
        
        if request.form['emargement'] == "Marquer l'heure de départ":
            start = time.strftime('%H:%M:%S', time.localtime())
            startrecord= Registre(day=today, startTime=start, apprenant=user)
            db.session.add(startrecord)
            db.session.commit()
            message = "Votre heure de départ a bien été enregistrée."
            print(message)
            return render_template('profile.html', lastname = user.lastName, firstnames = user.firstNames , message = message, userId=userId)
        
        elif request.form['emargement'] == "Marquer l'heure de fin":
            end = time.strftime('%H:%M:%S', time.localtime())
            endrecord = Registre.query.filter_by(day=today).update(dict(endTime=end))
            db.session.commit()
            message = "Votre heure de fin a bien été enregistrée."
            return render_template('profile.html', lastname = user.lastName, firstnames = user.firstNames,  message = message, userId=userId)
               

@app.route('/logout')
def logout():
    return redirect(url_for('index'))



if __name__ == '__main__':
    app.run(port=5005, debug=True)
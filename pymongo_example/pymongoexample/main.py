from flask import Blueprint, jsonify, request,current_app as app, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from .extensions import mongo 
import jwt
import face_recognition
import os
import atexit
import numpy as np
from bson.objectid import ObjectId
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import numpy as np
from functools import wraps

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'png','jpg','jpeg'}
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process():
    waiters = mongo.db.waiters.find({'type' : 'waiting'})
    if(len(list(waiters)) > 0):
        for x in mongo.db.waiters.find({'type' : 'waiting'}):
            path1 = './pymongoexample/encoded_images/{0}/{0}_1.txt'.format(x['username'])
            path2 = './pymongoexample/waiter_images/{0}.txt'.format(x['_id'])
            if(os.path.isfile(path1) and os.access(path1, os.R_OK) and os.path.isfile(path2) and os.access(path2, os.R_OK)):
                faceA = np.loadtxt(path1)
                faceB = np.loadtxt(path2)

                result = face_recognition.face_distance([faceA],faceB)
        
                if result < 0.4056358:
                    try:
                        print(x['username'] + ' is recognized')
                        mongo.db.waiters.update_one({'_id' : x['_id']},{'$set' : {'type' : 'attended'}})
                        os.remove(path2)
                    except:
                        print("error1")
                else:
                    try:
                        print(x['username']+ ' is fail to recognized')
                        mongo.db.waiters.update_one({'_id' : x['_id']},{'$set' : {'type' : 'fail'}})
                        os.remove(path2)
                        
                    except:
                        print("error2")
            else:
                print('File is not ready')

scheduler = BackgroundScheduler()
scheduler.add_job(func=process,trigger="interval", seconds=7)
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))


@main.route('/ss')
def s():
    print(app.config['UPLOAD_FOLDER'])
    return jsonify({}),200

@main.route('/login', methods=['POST'])
def login():
    req_data = request.get_json()

    if not req_data['username'] or not req_data['password']:
        msg = {'status' : {'type' : 'failure', 'message' : 'somethings is wrong'}}
        return jsonify(msg),200

    user = mongo.db.users.find_one({'username' : req_data['username']})

    if user is None:
        msg = {'status' : {'type' : 'failure', 'message' : 'user not found'}}
        return jsonify(msg),200

    check = check_password_hash(user['password'], req_data['password'])

    if check:
        token_data = {
                'username' : req_data['username'],
        }
        token = jwt.encode(token_data,app.config['SECRET_KEY'])
        return jsonify({'token' : token.decode('UTF-8'),'username' : user['username'],'firstname' : user['firstname'],'lastname' : user['lastname'],'verified' : user['verified'], 'status' : {'type' : 'success'}}),200
    else:
        msg = {'status' : {'type' : 'failure', 'message' : 'wrong password'}}
        return jsonify(msg),200

@main.route('/register1', methods=['POST'])
def register1():

    found = mongo.db.users.find_one({'username' : request.form.get('username')})

    if not found:
        return jsonify({'msg' : 'user is valid'}),201
    else:
        return jsonify({'msg' : 'user already exist'}),200

@main.route('/register2', methods=['POST'])
def register2():
    username = request.form.get('username')
    password = request.form.get('password')
    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')
    profile_image = request.files['profile_image']

    if not username or not password:
        msg = {'status' : {'type' : 'failure', 'message' : 'somethings is wrong'}}
        return jsonify(msg),200

    if 'profile_image' not in request.files:
        msg = {'status' : {'type' : 'failure', 'message' : 'no file part'}}
        return jsonify(msg),200
    
    if profile_image.filename == '':
        return jsonify({'msg' : 'no file selected'}),200

    

    if profile_image and allowed_file(profile_image.filename):
        unknown_img = face_recognition.load_image_file(profile_image)
        unknown_img_encodings = face_recognition.face_encodings(unknown_img)
        if len(unknown_img_encodings) > 0:
            unknown_face_encoding = unknown_img_encodings[0]
            hash_password = generate_password_hash(password)
        
            _id = mongo.db.users.insert_one({
                'username' : username,
                'password' : hash_password,
                'verified' : False,
                'firstname' : firstname,
                'lastname' : lastname,
                'events' : [],
            })

            try:
                os.chdir(app.config['UPLOAD_FOLDER'])
                os.mkdir('{foldername}'.format(foldername = _id.inserted_id))
                _dir = os.path.join(app.config['UPLOAD_FOLDER'],'{foldername}'.format(foldername = _id.inserted_id))
                file_count = len(os.listdir(_dir)) + 1
                np.savetxt('{0}\{1}\{1}_{2}.txt'.format(app.config['UPLOAD_FOLDER'], _id.inserted_id, file_count),unknown_face_encoding, fmt='%s')
                return jsonify({'msg' : 'register success!'}),200
            except OSError:
                return jsonify({'msg' : 'something is wrong'}),200
        else:
            return jsonify({'msg' : 'face was not found in the image'}),200
    else:
        return jsonify({'msg' : 'bad file type'}),200

@main.route('/save_image', methods=['POST'])
def send_image():
    profile_image = request.files['profile_image']
    username = request.form.get('_username')
    profile_image.save('{0}\{1}.jpeg'.format(app.config['PROFILE_IMAGE_FOLDER'], username))
    return jsonify({}),200

@main.route('/check_image', methods=['POST'])
def update_image():
    profile_image = request.files['profile_image']
    username = request.form.get('_username')
    unknown_img = face_recognition.load_image_file(profile_image)
    unknown_img_encodings = face_recognition.face_encodings(unknown_img)
    if len(unknown_img_encodings) > 0:
        unknown_face_encoding = unknown_img_encodings[0]
        user = mongo.db.users.find_one({'username' : username})
        np.savetxt('{0}\{1}\{1}_1.txt'.format(app.config['UPLOAD_FOLDER'], str(user['_id'])),unknown_face_encoding, fmt='%s')
        return jsonify({'msg' : 'success'}),201
    return jsonify({'msg' : 'no face was found'}),200
    
@main.route('/profile_image/<_username>')
def file(_username):
    return send_from_directory(app.config['PROFILE_IMAGE_FOLDER'], _username + '.jpeg')

@main.route('/read_qr', methods=['POST'])
def read_qr():
    req_data = request.get_json();

    event = mongo.db.events.find_one({'eventKey' : req_data['eventKey']})

    if event is None:
        return jsonify({'msg' : 'fake secret'}),200

    user = mongo.db.users.find_one({'username' : req_data['username'],'events' : ObjectId(str(event['_id']))})

    if user is not None:
        return jsonify(),201

    return jsonify({'msg' : 'found','event_name' : event['title']}),200

@main.route('/get_event/<username>', methods=['GET'])
def get_event(username):

    user = mongo.db.users.find_one({'username' : str(username)})
    waiter = mongo.db.waiters.find({'username' : ObjectId(str(user['_id']))})

   
    event_list = []
    for document in waiter:
        event = mongo.db.events.find_one({'_id' : document['event']})
        event_list.append({
            '_id' : str(document['_id']),
            'date_time' : document['date'],
            'event_type' : document['type'],
            'event_name' : event['title'],
            'verified' : user['verified']
        })
    
    event_list.reverse()
    return jsonify(event_list),200

@main.route('/join_event', methods=['POST'])
def join_event():
    if 'file' not in request.files:
        msg = {'status' : {'type' : 'failure', 'message' : 'no file part'}}
        return jsonify({msg}),200
    
    username = request.form.get('username')
    eventKey = request.form.get('eventKey')
    file = request.files['file']

    event = mongo.db.events.find_one({'eventKey' : eventKey})

    user = mongo.db.users.find_one({'username' : username})


    if file and allowed_file(file.filename):
        unknown_face = face_recognition.load_image_file(file)
        unknown_face_decoding = face_recognition.face_encodings(unknown_face)
        if len(unknown_face_decoding) > 0:
            unknown_face_encoded = unknown_face_decoding[0]
            _id = mongo.db.waiters.insert_one({'username' : user['_id'],'event' : event['_id'],'type' : '','date' : datetime.today().strftime('%Y-%m-%d %A')})
            try:
                np.savetxt('{0}\{1}.txt'.format(app.config['WAITER_FOLDER'], _id.inserted_id),unknown_face_encoded, fmt='%s')
                mongo.db.waiters.update_one({'_id' : ObjectId(_id.inserted_id)},{'$set' : {'type' : 'waiting'}})
                mongo.db.events.update_one({'eventKey' : eventKey},{'$push' : {'attendees' : _id.inserted_id}})
                mongo.db.users.update_one({'username' : username},{'$push' : {'events' : event['_id']}})
                return jsonify({}),200
            except OSError:
                print(OSError)
                return jsonify({}),200
        else:
            return jsonify({}),201
    else:
        return jsonify({}),201

@main.route('/verified', methods=['POST'])
def verified():
    req_data = request.get_json()
    
    try:
        waiter = mongo.db.waiters.find_one({'_id' : ObjectId(req_data['waiter'])})
    except:
        return jsonify({'msg' : 'invalid qrcode'}),201

    if waiter is None:
        return jsonify({'msg' : 'not found'}),200

    if req_data['waiter']:
        mongo.db.waiters.update_one({'_id' : ObjectId(req_data['waiter'])},{'$set' : {'type' : 'attended'}})
    
    return jsonify({'msg' : 'success'}),200




def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.form.get('token')
        
        if not token:
            return jsonify({'msg' : 'missing token'}),200

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
            print(data)
        except:
            return jsonify({'msg' : 'Token is invalid'}),200
        
        return f(*args, **kwargs)
    
    return decorated_function

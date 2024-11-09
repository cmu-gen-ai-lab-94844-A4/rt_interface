from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file # type: ignore
from flask import render_template_string # type: ignore
from flask_dance.contrib.github import make_github_blueprint, github
import requests # type: ignore
#from flask_oauthlib.provider import OAuth2Provider # type: ignore
from authlib.integrations.flask_client import OAuth # type: ignore
from flask_session import Session # type: ignore
from flask_cors import CORS # type: ignore
from flask_wtf import CSRFProtect # type: ignore
from flask_wtf.csrf import CSRFError # type: ignore


import huggingface_hub, torch, datasets 
from transformers import pipeline
from json import loads, dumps

import openai, logging, os, socket, csv, json, random, uuid # type: ignore
from datetime import datetime, timedelta
from io import BytesIO, StringIO

import psycopg2 # type: ignore
import psycopg2.extras # type: ignore
from psycopg2 import pool # type: ignore

# Load .env file
from dotenv import load_dotenv # type: ignore
load_dotenv()


# Define Flask application
app = Flask(__name__, template_folder='templates')

# Flask-Session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=90)
app.config.from_object(__name__)

# Initialize Flask-Session
Session(app)
CORS(app)
oauth = OAuth(app)

# Check if the secret key is being fetched properly from the environment
secret_key = os.getenv('app_key')
if not secret_key:
    raise RuntimeError("No secret key set for Flask application. Please set 'app_key' in the .env file.")
app.secret_key = secret_key  # Ensure secret_key is set

# Establish logging configuration
logging.basicConfig(
    filename='record.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
)

''' 
# Configure GitHub OAuth using Flask-Dance
github_bp = make_github_blueprint(
    client_id=os.getenv('GITHUB_OAUTH_CLIENT_ID'),
    client_secret=os.getenv('GITHUB_OAUTH_CLIENT_SECRET'),
)

# Register the GitHub OAuth blueprint with a proper prefix
app.register_blueprint(github_bp, url_prefix='/github_login')
'''

# define keys for environmental resources used by the application:
my_secret_url = os.environ['DATABASE_URL']
my_secret_pw = os.environ['PGPASSWORD']
#pg_user = os.environ['PGUSER']
#pg_host = os.environ['PGHOST']
#pg_connection_string = os.environ['PGCONNECTIONSTRING']

############ database connection pool ############
# Create a connection pool 
def get_postgres_connection_pool():
    try:
        # Use the connection string directly
        connection_string = os.environ['PGCONNECTIONSTRING']

        # Create a connection pool
        #pg_pool = psycopg2.pool.SimpleConnectionPool(1, 10, dsn=connection_string)  # Adjust minconn and maxconn as needed
        pg_pool = psycopg2.pool.SimpleConnectionPool(1, 10, dsn=my_secret_url)

        if pg_pool:
            print("Connection pool created successfully")

        # Get a connection from the pool
        connection = pg_pool.getconn()
        if connection:
            print("Successfully received connection from pool")

        return pg_pool, connection

    except (Exception, psycopg2.DatabaseError) as error:
        print("Error while connecting to PostgreSQL", error)

pg_pool, connection = get_postgres_connection_pool()

##### DATABASE / TABLE CREATION AND CALLING FUNCTIONS ##### 

def init_user_rt_data_db():
    pg_pool, connection = get_postgres_connection_pool()
    c = connection.cursor()

    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS genailab_users (
                id INTEGER PRIMARY KEY,
                user_id VARCHAR, 
                user_name VARCHAR, 
                user_email VARCHAR, 
                team_id VARCHAR, 
                team_name VARCHAR, 
                userid_created TIMESTAMPTZ,
                userid_last_login TIMESTAMPTZ);''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS genailab_session_ids (
                session_id serial PRIMARY KEY, 
                user_id VARCHAR, 
                team_id VARCHAR, 
                session_start_datetime TIMESTAMPTZ, 
                session_end_datetime TIMESTAMPTZ);''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS models_selected (
                 id INTEGER PRIMARY KEY,
                 user_id TEXT,
                 session_id VARCHAR,
                 model_name TEXT,
                 timestamp TIMESTAMPTZ);''')

    c.execute('''CREATE TABLE IF NOT EXISTS prompts_responses (
                 id INTEGER PRIMARY KEY,
                 user_id TEXT,
                 session_id VARCHAR,
                 prompt TEXT,
                 response TEXT,
                 model_name TEXT,
                 timestamp_prompt_submitted TIMESTAMPTZ,
                 timestamp_aiResponse_received TIMESTAMPTZ);''')

    c.execute('''CREATE TABLE IF NOT EXISTS evaluations (
                 id INTEGER PRIMARY KEY,
                 user_id TEXT,
                 session_id VARCHAR,
                 response TEXT,
                 correct TEXT,
                 score INTEGER,
                 explanation TEXT,
                 timestamp TIMESTAMPTZ);''')

    connection.commit()
    pg_pool.putconn(connection)
  

# Call init_db to make sure the database is set up
init_user_rt_data_db()
logging.info("Initialized user_rt_data database")
  
def get_user_id_genailab(user_id):
  pg_pool, connection = get_postgres_connection_pool()
  cursor = connection.cursor()
  cursor.execute('''SELECT user_id FROM genailab_users WHERE user_id= %s;''', (user_id,))
  user_ids = cursor.fetchall()
  pg_pool.putconn(connection)
  return user_id
  
##### CUSTOM FUNCTIONS
# This function can be used to generate a unique session ID
def generate_session_id():
    return str(uuid.uuid4())


###### APPLICATION ROUTING ######

#@app.before_request
#def make_session_permanent():
    """
    Ensure the session is permanent and initialize the chat log if it doesn't exist.
    """
   # session.permanent = True
   # if 'chat_log' not in session:
        #session['chat_log'] = []
        
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        #make_session_permanent()
        session['session_id'] = generate_session_id()
        session['user_id'] = request.form.get('user_id')
        session['team_name'] = request.form.get('team_name')
        session['first_name'] = request.form.get('first_name')
        session['email'] = request.form.get('email')
        user = session.get('user_id')
        logging.info(f"User {user} initiated registration.")
        #return redirect(url_for('github.login'))
        return redirect(url_for('user_dashboard', user_id=user))
    else:
        return render_template('index.html')
    
'''
@app.route('/register', methods=['POST'])
def register():
    # Save user registration details in the session or database
    session['user_id'] = request.form['user_id']
    session['team_name'] = request.form.get('team_name')  # Optional field
    session['first_name'] = request.form['first_name']
    session['email'] = request.form['email']
    
    # Render or redirect to a page for selecting OAuth provider
    return redirect(url_for('select_login_method'))  # Assumes you have a view for selecting OAuth

@app.route('/select_login_method')
def select_login_method():
    # Render a template where the user selects GitHub or Hugging Face login
    return render_template('select_login.html')  # Use a template to guide the user to choose OAuth

# No need to change GitHub or Hugging Face login routes since they are already set
# Users will choose the login they want after registration

# Configure Hugging Face OAuth
huggingface = oauth.register(
    name='huggingface',
    client_id=os.getenv('HUGGINGFACE_CLIENT_ID'),
    client_secret=os.getenv('HUGGINGFACE_CLIENT_SECRET'),
    access_token_url='https://huggingface.co/oauth/token',
    authorize_url='https://huggingface.co/login/oauth/authorize',
    api_base_url='https://huggingface.co/api/',
    client_kwargs={
        'scope': 'user:email',
    }
)

@app.route('/huggingface/login')
def huggingface_login():
    redirect_uri = url_for('huggingface_auth', _external=True)
    app.logger.debug("Handling /huggingface/login")
    app.logger.debug("Initiating OAuth login with state: {}".format(session.get('state')))
    return huggingface.authorize_redirect(redirect_uri)

@app.route('/huggingface/auth')
def huggingface_auth():
    # Debug the state value received
    app.logger.debug("Handling /huggingface/auth")
    app.logger.debug("Received state from OAuth: {}".format(request.args.get('state')))
    # Try-catch error block to detect where the problem occurs
    try:
        token = huggingface.authorize_access_token()
        user_info = huggingface.get('user')
        session['huggingface_user'] = user_info.json()
        return redirect(url_for('user_dashboard'))
    except Exception as e:
        app.logger.error(f"OAuth error: {str(e)}")
        return f"Authentication failed: {str(e)}", 401
    

@app.route('/github/login')
def github_login():
    if not github.authorized:
        return redirect(url_for('github.login'))
    resp = github.get('/user')
    if not resp.ok:
        return f"Failed to fetch user information: {resp.text}", 500

    # User is authorized, carry user information to the dashboard
    gh_user_info = resp.json()
    session['github_user'] = gh_user_info
    return redirect(url_for('user_dashboard'))
'''

@app.route('/user_dashboard')
def user_dashboard():
    user_id = session['user_id']
    session_id = session['session_id']
    timestamp = datetime.now()
    #github_user_info = session.get('github_user')
    #huggingface_user_info = session.get('huggingface_user')

    #if not github_user_info and not huggingface_user_info:
        #return redirect(url_for('home'))
    return render_template('user_dashboard.html')
    #return render_template(
        #'user_dashboard.html',
        #github_user_info=github_user_info,
        #huggingface_user_info=huggingface_user_info
    #)


@app.route('/text_gen', methods=['GET', 'POST'])
def text_gen():
    if request.method == 'POST':
        try:
            user_id = session.get['user_id']
            session_id = session.get['session_id']
            timestamp = datetime.now()
            logging.info(f"User {user_id} started tex_gen at: {timestamp}")
        except Exception as e:
            logging.error(f"Error starting tex_gen_rt: {str(e)}")
            return jsonify({'next': False})
        return jsonify({'next': True})
    else:
        return render_template('text_gen.html')
    
@app.route('/text_gen_02', methods=['GET', 'POST'])
def text_gen_02():
    if request.method == 'POST':
        try:
            user_id = session.get['user_id']
            session_id = session.get['session_id']
            timestamp = datetime.now()
            logging.info(f"User {user_id} started tex_gen_02 at: {timestamp}")
        except Exception as e:
            logging.error(f"Error starting tex_gen_rt_02: {str(e)}")
            return jsonify({'next': False})
        return jsonify({'next': True})
    else:
        return render_template('text_gen_02.html')
    
@app.route('/text_gen_03', methods=['GET', 'POST'])
def text_gen_03():
    if request.method == 'POST':
        try:
            user_id = session.get['user_id']
            session_id = session.get['session_id']
            timestamp = datetime.now()
            logging.info(f"User {user_id} started tex_gen_03 at: {timestamp}")
        except Exception as e:
            logging.error(f"Error starting tex_gen_rt_03: {str(e)}")
            return jsonify({'next': False})
        return jsonify({'next': True})
    else:
        return render_template('text_gen_03.html')
    
@app.route('/text_gen_04', methods=['GET', 'POST'])
def text_gen_04():
    if request.method == 'POST':
        try:
            user_id = session.get['user_id']
            session_id = session.get['session_id']
            timestamp = datetime.now()
            logging.info(f"User {user_id} started tex_gen_04 at: {timestamp}")
        except Exception as e:
            logging.error(f"Error starting tex_gen_rt_04: {str(e)}")
            return jsonify({'next': False})
        return jsonify({'next': True})
    else:
        return render_template('text_gen_04.html')

@app.route('/reading')
def reading():
    return render_template('reading.html')

@app.route('/other_resources')
def other_resources():
    return render_template('other_resources.html')

######################## APPLICATION API ENDPOINTS ############################

# Handle model selection and store in session
@app.route('/select_model', methods=['POST'])
def select_model():
    model_name = request.json.get('modelName')
    print(model_name)
    
    # Extract the JSON data from the request
    data = request.get_json()
    print(data)
    
    # Extract the model name from the JSON data
    #model_name = data.get('modelName')

    session['model_name'] = model_name
    
    session_id = session.get('session_id')
    user_id = session.get('user_id')
    print(user_id)
    
    timestamp = datetime.now()
    
    #pg_pool, connection = get_postgres_connection_pool()
    #c = connection.cursor()
    #c.execute("INSERT INTO models_selected (user_id,session_id, model_name, timestamp) VALUES (?, ?, ?, ?)", (user_id, session_id, model_name, timestamp))
    #connection.commit()
   #pg_pool.putconn(connection)
    return jsonify({"status": "success", "message": f"Model {model_name} selected"}, model_name)

# Handle evaluation form submissions
@app.route('/submit_evaluation', methods=['POST'])
def submit_evaluation():
    #form_data = request.form
    user_id = session.get('user_id')
    session_id = session.get('session_id')
    
    form_data = request.get_json()
    response = form_data.get('response')
    correct = form_data.get('correct')
    score = int(form_data.get('score', 0))
    explanation = form_data.get('explanation')
    timestamp = datetime.now()

    #pg_pool, connection = get_postgres_connection_pool()
    #c = connection.cursor()
    #c.execute("INSERT INTO evaluations (user_id, session_id, response, correct, score, explanation, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
              #(user_id, session_id, response, correct, score, explanation, timestamp))
    #connection.commit()
    #pg_pool.putconn(connection)

    return jsonify({"status": "success", "message": "Evaluation submitted successfully"})

# handle LLM chat messages:
@app.route('/api/handle_message', methods=['POST'])
def handle_message():
    try:
        payload = request.get_json()
        message = payload['message']
        user_message = payload['message']
        #user_message= message
        
        user_id = session.get('user_id')
        logging.info(f"Handling message for user {user_id}: {message}")
        
        session_id = session.get('session_id')
        logging.info(f"Retrieved current session_id for {user_id}")
        
        timestamp_prompt_submitted = datetime.now().isoformat()
        logging.info(f"Created timestamp for prompt submitted to llm model by {user_id}")
        

        # Extract the JSON data from the request
        data = request.get_json()
    
        # Extract the model name from the JSON data
        #model_name = data.get('modelName')
        model_name = request.json.get('modelName')
        logging.info(f"Retrieved model name selected by {user_id}")
        
        if model_name == 'Llama':
            ai_response = get_llama_response(message)
        else:
            ai_response = get_ai_response(message)
        logging.info(f"Generated ai_response to {user_id} prompt")
        
        response = ai_response
        timestamp_aiResponse_received = datetime.now().isoformat()
        logging.info(f"Created ai_response timestamp for ai_response to {user_id}")
        
        # Initialize chat_log if it doesn't already exist
        if 'chat_log' not in session:
            session['chat_log'] = []
            
        # Add record to session chat log
        session['chat_log'].append({
            'user_id': user_id,
            'session_id': session_id,
            'user_message': message,
            'ai_response': response,
            'mode_name': model_name,
            'timestamp_prompt_submitted': timestamp_prompt_submitted,
            'timestamp_aiResponse_received': timestamp_aiResponse_received
        })
        logging.info(f"Added chat log record for user {user_id} to session log")
        
        #pg_pool, connection = get_postgres_connection_pool()
        #c = connection.cursor()
        #c.execute("INSERT INTO prompts_responses (user_id, session_id, prompt, response, model_name, timestamp_prompt_submitted, timestamp_aiResponse_received) VALUES (?, ?, ?, ?, ?, ?, ?)", 
              #  (user_id, session_id, message, response, model_name, timestamp_prompt_submitted, timestamp_aiResponse_received))
        #connection.commit()
        #pg_pool.putconn(connection)
        
        logging.info(f"Added chat log record for user {user_id} to PostGres database")
        
        return jsonify({"response": response}) 
        #return jsonify({"response": ai_response})
    except Exception as e:
        logging.error(f"Error in handling message: {str(e)}", exc_info=True)
        return jsonify({"response": "Error in processing your message. Please try again."})
    


def get_ai_response(message):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("No OpenAI API key found in the environment variables. Please set 'OPENAI_API_KEY' in the .env file.")
    
    openai.api_key = openai_api_key
    
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Respond to this {message}"},
            {"role": "user", "content": message}])

    response=response.choices[0].message.content
    
    timestamp_aiResponse_received = datetime.now().isoformat()
    session[' timestamp_aiResponse_received'] =  timestamp_aiResponse_received
    
    return response


def get_llama_response(message):
    from dotenv import load_dotenv
    load_dotenv()
    
    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
    if not HF_TOKEN:
        raise RuntimeError("No Hugging Face API token found in the environment variables. Please set 'HUGGINGFACE_TOKEN' in the .env file.")

    pipe = pipeline("text-generation", model="meta-llama/Llama-3.2-1B", token=HF_TOKEN)  

    if isinstance(message, str):
        messages = [message]  # Convert the single prompt to a list

    responses = []
    system_prompt = "Provide a response to the user."

    for prompt in messages:
        # Generate response from the LLM
        try:
            # Assuming the model can handle single string inputs as well
            outputs = pipe(f"{system_prompt} {prompt}", max_length=150, num_return_sequences=1, truncation=True)
            response = outputs[0]["generated_text"]
            responses.append(response)
        except Exception as e:
            responses.append(f"Error generating response: {e}")

    return responses if len(responses) > 1 else responses[0]  # Return a single response or a list



''' dysfunctional code:
def get_llama_response(message):
    from dotenv import load_dotenv
    load_dotenv()

    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
    if not HF_TOKEN:
        raise RuntimeError("No Hugging Face API token found in the environment variables. Please set 'HUGGINGFACE_TOKEN' in the .env file.")

    pipe = pipeline("text-generation", model="meta-llama/Llama-3.2-1B", use_auth_token=HF_TOKEN)

    system_prompt = "Provide a response to the user."
    try:
        outputs = pipe(f"{system_prompt} {message}", max_length=500, num_return_sequences=1)
        response = outputs[0]["generated_text"]
    except Exception as e:
        response = f"Error generating response: {e}"

    return response
 '''   
    

def send_file_compatibility(data, mimetype, filename):
    output = BytesIO()
    output.write(data.encode('utf-8'))
    output.seek(0)
    try:
        return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)
    except TypeError:
        return send_file(output, mimetype=mimetype, as_attachment=True, attachment_filename=filename)

@app.route('/download/json', methods=['GET'])
def download_json():
    chat_log = session.get('chat_log', [])
    data = json.dumps(chat_log, indent=4)
    return send_file_compatibility(data, mimetype='application/json', filename='chat_history.json')

@app.route('/download/csv', methods=['GET'])
def download_csv():
    chat_log = session.get('chat_log', [])
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['user_id', 'session_id','user_message', 'ai_response', 'mode_name', 'timestamp_prompt_submitted', 'timestamp_aiResponse_received'])
    for record in chat_log:
        writer.writerow([record['user_id'],record['session_id'], record['user_message'], record['ai_response'], record['model_name'], record['timestamp_prompt_submitted'], record['timestamp_aiResponse_received']])
    output.seek(0)
    return send_file(BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='chat_history.csv')



if __name__ == "__main__":
    port = int(os.getenv('PORT', 10000))
    app.run(debug=True, host='0.0.0.0', port=port)



    

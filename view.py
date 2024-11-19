from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file # type: ignore
from flask import render_template_string # type: ignore
from flask_dance.contrib.github import make_github_blueprint, github # type: ignore
import requests # type: ignore
#from flask_oauthlib.provider import OAuth2Provider # type: ignore
from authlib.integrations.flask_client import OAuth # type: ignore
from flask_session import Session # type: ignore
from flask_cors import CORS # type: ignore
from flask_wtf import CSRFProtect # type: ignore
from flask_wtf.csrf import CSRFError # type: ignore
import huggingface_hub, torch, datasets # type: ignore
from huggingface_hub import InferenceClient # type: ignore
from transformers import pipeline # type: ignore
from json import loads, dumps

from collections import deque

import openai, logging, os, socket, csv, json, random, uuid # type: ignore
from datetime import datetime, timedelta
from io import BytesIO, StringIO

# database packages:
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
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=120)
app.config.from_object(__name__)

# Initialize Flask-Session
Session(app)
CORS(app)
#oauth = OAuth(app)

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

# define keys for environmental resources used by the application:
my_secret_url = os.environ['DATABASE_URL']
my_secret_pw = os.environ['PGPASSWORD']

############ database connection pool ############

# Create a connection pool 
def get_postgres_connection_pool():
    try:
        # Use the connection string directly
        my_secret_url = os.environ['DATABASE_URL']

        # Create a connection pool
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
    c.execute('''CREATE TABLE IF NOT EXISTS genailab_users2 (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR, 
                user_name VARCHAR, 
                user_email VARCHAR, 
                team_id VARCHAR,  
                userid_last_login TIMESTAMP);''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS genailab_session_ids2 (
                sys_session_id SERIAL PRIMARY KEY, 
                session_id VARCHAR, 
                user_id VARCHAR, 
                team_id VARCHAR, 
                session_start_datetime TIMESTAMP, 
                session_end_datetime TIMESTAMP);''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS models_selected2 (
                 model_selection_id SERIAL PRIMARY KEY,
                 user_id VARCHAR,
                 session_id VARCHAR,
                 model_name VARCHAR,
                 timestamp TIMESTAMP);''')

    c.execute('''CREATE TABLE IF NOT EXISTS prompts_responses3 (
                 prompts_responses_id SERIAL PRIMARY KEY,
                 user_id VARCHAR,
                 session_id VARCHAR,
                 prompt VARCHAR,
                 prompt_id VARCHAR,
                 response VARCHAR,
                 response_id VARCHAR,
                 model_name VARCHAR,
                 timestamp_prompt_submitted TIMESTAMP,
                 timestamp_aiResponse_received TIMESTAMP);''')

    c.execute('''CREATE TABLE IF NOT EXISTS evaluations2 (
                 evaluation_id SERIAL PRIMARY KEY,
                 user_id VARCHAR,
                 session_id VARCHAR,
                 response VARCHAR,
                 correct VARCHAR,
                 score INTEGER,
                 explanation VARCHAR,
                 timestamp TIMESTAMP);''')

    connection.commit()
    pg_pool.putconn(connection)
    
# insert content into database
def insert_into_model_selected(user_id, session_id, response, correct, score, explanation, timestamp):
    pg_pool, connection = get_postgres_connection_pool()
    c = connection.cursor()
    c.execute("INSERT INTO models_selected2 (user_id, session_id, model_name, timestamp) VALUES (%s, %s, %s, %s)",
              (user_id, session_id, response, correct, score, explanation, timestamp))
    connection.commit()
    pg_pool.putconn(connection)

def insert_into_evaluations(user_id, session_id, response, correct, score, explanation, timestamp):
    pg_pool, connection = get_postgres_connection_pool()
    c = connection.cursor()
    c.execute("INSERT INTO evaluations (user_id, session_id, response, correct, score, explanation, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)",
              (user_id, session_id, response, correct, score, explanation, timestamp))
    connection.commit()
    pg_pool.putconn(connection)
    
def insert_into_user_rt_data(user_id, user_name, user_email, team_id, team_name, userid_created, userid_last_login):
    pg_pool, connection = get_postgres_connection_pool()
    c = connection.cursor()
    c.execute("INSERT INTO genailab_users (user_id, user_name, user_email, team_id, team_name, userid_created, userid_last_login) VALUES (%s, %s, %s, %s, %s, %s, %s)",
              (user_id, user_name, user_email, team_id, team_name, userid_created, userid_last_login))
    connection.commit()
    pg_pool.putconn(connection)
    
# retrieve database content

def get_most_recent_model_name():
    pg_pool, connection = get_postgres_connection_pool()
    c = connection.cursor()
    c.execute("SELECT model_name FROM models_selected2 ORDER BY timestamp LIMIT 1;")
    model_name = c.fetchall()
    pg_pool.putconn(connection)
    return model_name

  

# Call init_db to make sure the database is set up

init_user_rt_data_db()
logging.info("Initialized user_rt_data database")
  

##### CUSTOM FUNCTIONS
# This function can be used to generate a unique session ID
def generate_session_id():
    return str(uuid.uuid4())

def generate_conversation_id():
    return str(uuid.uuid4())

def generate_prompt_id():
    return str(uuid.uuid4())

def generate_llm_response_id():
    return str(uuid.uuid4())


###### APPLICATION ROUTING ######

@app.before_request
def make_session_permanent():
    """
    Ensure the session is permanent and initialize the chat log if it doesn't exist.
    """
    session.permanent = True
    if 'chat_log' not in session:
        session['chat_log'] = []
        
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        
        #make_session_permanent()
        
        session_id = generate_session_id()
        session['session_id'] = session_id

        userid_last_login = datetime.now()
        session_id = session.get('session_id')
        
        user_id = request.form.get('andrew_id')
        logging.info(f"User {user_id} initiated registration.")
        
        # get user_id from form
        session['user_id'] = user_id
        
        team_id = request.form.get('team_id')
        
        first_name = request.form.get('first_name')
        
        user_cmu_email = request.form.get('cmu_email')
        
        session['team_id'] = team_id
        session['first_name'] = first_name 
        session['user_email'] =  user_cmu_email
        
        pg_pool, connection = get_postgres_connection_pool()
        cursor = connection.cursor()
        
        cursor.execute("INSERT INTO genailab_users2 (user_id, user_name, user_email, team_id, userid_last_login) VALUES (%s, %s, %s, %s, %s);", (user_id, first_name, user_cmu_email, team_id, userid_last_login))
        
        pg_pool.putconn(connection)
        
        #return redirect(url_for('github.login'))
        return redirect(url_for('user_dashboard'))
    else:
        return render_template('index.html')

@app.route('/user_dashboard')       # fixme: add table to database to store challenge selection
def user_dashboard():
    user_id = session.get('user_id')
    session_id = session.get('session_id')
    timestamp = datetime.now()
    return render_template('user_dashboard.html')

@app.route('/text_gen', methods=['GET', 'POST'])
def text_gen():
    if request.method == 'POST':
        try:
            user_id = session.get('user_id')
            session_id = session.get('session_id')
            #model_name = session.get('modelName')
            model_name = request.form.get('modelName')
            print(model_name)
            conversation_id = generate_conversation_id()
            prompt_id = generate_prompt_id()
            resonse_id = generate_llm_response_id()
            timestamp = datetime.now()
            logging.info(f"User {user_id} started tex_gen at: {timestamp}")
        except Exception as e:
            logging.error(f"Error starting tex_gen_rt: {str(e)}")
            return jsonify({'next': False})
        return jsonify({'next': True, 'model_name': model_name})
    else:
        return render_template('text_gen.html')
    
@app.route('/text_gen_02', methods=['GET', 'POST'])
def text_gen_02():
    if request.method == 'POST':
        try:
            print("Session data:", session)
            user_id = session.get('user_id')
            session_id = session.get('session_id')
            timestamp = datetime.now()
            logging.info(f"User {user_id} started text_gen_02 at: {timestamp}")
        except Exception as e:
            logging.error(f"Error starting text_gen_rt_02: {str(e)}")
            return jsonify({'next': False})
        return jsonify({'next': True})
    else:
        return render_template('text_gen_02.html')
    
@app.route('/text_gen_03', methods=['GET', 'POST'])
def text_gen_03():
    if request.method == 'POST':
        try:
            user_id = session.get('user_id')
            session_id = session.get('session_id')
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
            user_id = session.get('user_id')
            session_id = session.get('session_id')
            timestamp = datetime.now()
            logging.info(f"User {user_id} started tex_gen_04 at: {timestamp}")
        except Exception as e:
            logging.error(f"Error starting tex_gen_rt_04: {str(e)}")
            return jsonify({'next': False})
        return jsonify({'next': True})
    else:
        return render_template('text_gen_04.html')



######################## APPLICATION API ENDPOINTS ############################

@app.route('/api/mark_safe/<int:response_id>', methods=['POST'])
def mark_safe(response_id):
    try:
        # psuedo-code:
        '''
        - get response_id from the URL
        - mark the response as safe in the database
        - return a success message
        '''
        
        return jsonify({'message': f'Response {response_id} marked as safe'}), 200
    except Exception as e:
        logging.error(f"Error marking response as safe: {str(e)}")
        return jsonify({'error': 'An error occurred while marking the response as safe'}), 500


@app.route('/api/select_model', methods=['POST'])
def select_model():
    try:
        model_name = request.form.get('model-selection-form')

        #if model_name:
           # session['model_name'] = model_name
           # print("Model name set in session")
        #else:
           # print("modelName key not found in request_data")
        
        # Initialize or update the list of selected models in session
        if 'modelNameList' not in session:
            session['modelNameList'] = []
        
        # Append the model name to the session's modelNameList
        session['modelNameList'].append(model_name)
        
        model_name = session.get('modelNameList')[-1]
        

        # Get user and session details
        user_id = session.get('user_id')
        session_id = session.get('session_id')
        timestamp = datetime.now()

        # Database operations
        pg_pool, connection = get_postgres_connection_pool()
        c = connection.cursor()
        c.execute(
            "INSERT INTO models_selected2 (user_id, session_id, model_name, timestamp) VALUES (%s, %s, %s, %s);",
            (user_id, session_id, model_name, timestamp)
        )
        connection.commit()
        pg_pool.putconn(connection)

        return jsonify({"status": "success", "message": f"Model {model_name} selected", 'next': True})
    
    except Exception as e:
        logging.error(f"Error selecting model: {str(e)}", exc_info=True)
        return jsonify({"status": "failure", "message": "Failed to select model", "error": str(e)}), 400

# Handle evaluation form submissions
@app.route('/submit_evaluation', methods=['POST'])
def submit_evaluation():
    user_id = session.get('user_id')
    session_id = session.get('session_id')
    
    # Access form data
    user_prompt = request.form.get('user_message')
    response = request.form.get('response')
    correct = request.form.get('response_violation')  
    score = int(request.form.get('score', 0))
    explanation = request.form.get('explanation')
    timestamp = datetime.now()
    
    model_name = session.get('modelNameList')[-1]
    
    # Initialize chat log in session if it doesn't exist
    if 'evaluation_log' not in session:
        session['evaluation_log'] = []

    # Append current interaction to the chat log
    session['evaluation_log'].append({
        'user_id': user_id,
        'session_id': session_id,
        'grade': correct,
        'severity_score': score,
        'explanation': explanation,
        'prompt': user_prompt,
        'ai_response': response,
        'model_name': model_name,
        'evaluation_timestamp': timestamp
    })
    logging.info(f"Added evaluation log record for user {user_id}.")

    # Log information for debugging
    logging.info(f"Evaluation submitted by user: {user_id}, session: {session_id}, response: {response}, correct: {correct}, score: {score}, explanation: {explanation}")

    # database operations:
    pg_pool, connection = get_postgres_connection_pool()
    c = connection.cursor()
    c.execute("INSERT INTO evaluations2 (user_id, session_id, response, correct, score, explanation, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)",
           (user_id, session_id, response, correct, score, explanation, timestamp))
    connection.commit()
    pg_pool.putconn(connection)
    
    current_page = request.form.get('current_page')
    return redirect(current_page)
    #return redirect(url_for('text_gen'))


# handle LLM chat messages:
@app.route('/api/handle_message', methods=['POST'])
def handle_message():
    try:
        user_id = session.get('user_id')
        session_id = session.get('session_id')
        
        payload = request.get_json()
        message = payload.get('message')

        
        model_name = request.form.get('model_name')
        userModelSelectionList = []
        userModelSelectionList.append(model_name)
        session['userModelSelectionList'] = userModelSelectionList

        if model_name == 'Model01':
            ai_response = get_llama_response(message)
        elif model_name == 'Model02': 
            ai_response = get_ai_response(message)
        
        logging.info(f"Handling message for user {user_id}: {message} with model {model_name}")
        
        response = ai_response

        # Collect timestamps for the request and response handling
        timestamp_prompt_submitted = datetime.now().isoformat()
        timestamp_aiResponse_received = datetime.now().isoformat()

        # Initialize chat log in session if it doesn't exist
        if 'chat_log' not in session:
            session['chat_log'] = []

        # Append current interaction to the chat log
        session['chat_log'].append({
            'user_id': user_id,
            'session_id': session_id,
            'user_message': message,
            'ai_response': ai_response,
            'model_name': model_name,
            'timestamp_prompt_submitted': timestamp_prompt_submitted,
            'timestamp_aiResponse_received': timestamp_aiResponse_received
        })
        logging.info(f"Added chat log record for user {user_id}.")

        return jsonify({"response": response, "model_name": model_name})

    except Exception as e:
        logging.error(f"Error in handling message: {str(e)}", exc_info=True)
        return jsonify({"response": "Error in processing your message. Please try again."})
    

def serialize_for_json(data):
    # Check the type of each item
    if isinstance(data, list):
        return [serialize_for_json(item) for item in data]
    elif isinstance(data, dict):
        return {key: serialize_for_json(value) for key, value in data.items()}
    elif isinstance(data, datetime):
        return data.isoformat()  # Convert datetime to string
    else:
        return data
    
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
    timestamp_prompt_submitted = datetime.now().isoformat()
    prompt = message
    prompt_id = generate_prompt_id()
    user_id = session.get('user_id')
    session_id = session.get('session_id')

    response=response.choices[0].message.content
    response_id = generate_llm_response_id()
    
    prompt_response_log = {'prompt_id':'', 'response_id':'', 'user_id':'', 'session_id':'', 'prompt':'', 'ai_response':'', 'model_name':'', 'timestamp_prompt_submitted':'', 'timestamp_aiResponse_received':''}
    prompt_response_log['prompt_id'] = prompt_id
    prompt_response_log['response_id'] = response_id
    prompt_response_log['user_id'] = user_id
    prompt_response_log['session_id'] = session_id
    prompt_response_log['prompt'] = prompt
    prompt_response_log['ai_response'] = response
    prompt_response_log['model_name'] = "GPT-4o"
    prompt_response_log['timestamp_prompt_submitted'] = timestamp_prompt_submitted
    prompt_response_log['timestamp_aiResponse_received'] = datetime.now().isoformat()
    
    session['prompt_response_log'].append(prompt_response_log)

    model_name = "GPT-4o"
    
    # Initialize chat log in session if it doesn't exist
    if 'chat_log' not in session:
        session['chat_log'] = []

    # Append current interaction to the prompt_response log
    session['prompt_response_log'].append({
        'user_id': user_id,
        'session_id': session_id,
        'prompt': message,
        'prompt_id': prompt_id,
        'ai_response': response,
        'model_name': model_name,
        'timestamp_prompt_submitted': timestamp_prompt_submitted,
        'timestamp_aiResponse_received': timestamp_aiResponse_received
    })
    logging.info(f"Added prompt_response log record for user {user_id}.")
    
    pg_pool, connection = get_postgres_connection_pool()
    c = connection.cursor()
    c.execute("INSERT INTO prompts_responses3 (user_id, session_id, prompt, prompt_id, response, response_id, model_name, timestamp_prompt_submitted, timestamp_aiResponse_received) VALUES (%s,%s,%s, %s, %s, %s, %s, %s, %s)",
           (user_id, session_id, prompt, prompt_id, response, response_id, model_name, timestamp_prompt_submitted, timestamp_aiResponse_received))
    connection.commit()
    pg_pool.putconn(connection)
    
    timestamp_aiResponse_received = datetime.now().isoformat()
    session['timestamp_aiResponse_received'] =  timestamp_aiResponse_received
    
    return response, response_id


def get_llama_response(message):
    from dotenv import load_dotenv
    load_dotenv()

    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
    if not HF_TOKEN:
        raise RuntimeError("No Hugging Face API token found in the environment variables. Please set 'HUGGINGFACE_TOKEN' in the .env file.")
    
    client = InferenceClient(api_key=HF_TOKEN)
    
    messages = [
    {"role": "system", "content":  "Respond to this {message}"},
    {"role": "user", "content": message}]
    
    res = client.chat.completions.create(
    model="meta-llama/Meta-Llama-3-70B-Instruct", 
	messages=messages, 
	max_tokens=500,
	stream=False)
    
    llmResponse = res.choices[0].message['content']

    return llmResponse

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
    evaluation_log = session.get('evaluation_log', [])
    chat_log = session.get('chat_log', [])
    
    # Combine logs into a single dictionary
    combined_log = {
        'evaluation_log': serialize_for_json(evaluation_log),
        'chat_log': serialize_for_json(chat_log)
    }
    
    # Convert the combined logs to a JSON formatted string
    data = json.dumps(combined_log, indent=4)
    
    #data = json.dumps(chat_log, indent=4)
    return send_file_compatibility(data, mimetype='application/json', filename='chat_history.json')

@app.route('/download/csv', methods=['GET'])
def download_csv():
    evaluation_log = session.get('evaluation_log', [])
    chat_log = session.get('chat_log', [])

    # Create in-memory output file
    output = StringIO()
    writer = csv.writer(output)

    # Write CSV header
    writer.writerow([
        'user_id', 'session_id', 'user_message', 'model_name', 'ai_response',
        'grade', 'severity_score', 'explanation', 'timestamp_prompt_submitted',
        'timestamp_aiResponse_received', 'evaluation_timestamp'
    ])

    # Write chat log data
    for record in chat_log:
        writer.writerow([
            record.get('user_id', ''),
            record.get('session_id', ''),
            record.get('user_message', ''),
            record.get('model_name', ''),
            record.get('ai_response', ''),
            '',  # Placeholder for grade or any missing field
            '',  # Placeholder for severity_score or any missing field
            '',  # Placeholder for explanation or any missing field
            record.get('timestamp_prompt_submitted', ''),
            record.get('timestamp_aiResponse_received', '')
        ])

    # Write evaluation log data
    for item in evaluation_log:
        writer.writerow([
            '', '', '', '', '',
            item.get('grade', ''),
            item.get('severity_score', ''),
            item.get('explanation', ''),
            '',  # Placeholder is already filled for timestamps in previous log entry
            '', 
            item.get('evaluation_timestamp', '')
        ])

    # Reset the output buffer to read from the beginning
    output.seek(0)

    # Return file as a downloadable
    return send_file(BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='logs.csv')



if __name__ == "__main__":
    port = int(os.getenv('PORT', 10000))
    app.run(debug=True, host='0.0.0.0', port=port)



    

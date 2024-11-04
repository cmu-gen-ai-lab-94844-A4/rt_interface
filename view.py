from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file # type: ignore
from flask_dance.contrib.github import make_github_blueprint, github # type: ignore
from authlib.integrations.flask_client import OAuth # type: ignore
from flask_session import Session # type: ignore
from flask_cors import CORS # type: ignore

#import huggingface_hub
#from transformers import pipeline
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

# Check if the secret key is being fetched properly from the environment
secret_key = os.getenv('app_key')
if not secret_key:
    raise RuntimeError("No secret key set for Flask application. Please set 'app_key' in the .env file.")
app.secret_key = secret_key  # Ensure secret_key is set

# Flask-Session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=90)

# Initialize Flask-Session
Session(app)
CORS(app)
#oauth = OAuth(app)

# Establish logging configuration
logging.basicConfig(
    filename='record.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
)

git_client_id = os.getenv('GITHUB_OAUTH_CLIENT_ID')
git_client_secret = os.getenv('GITHUB_OAUTH_CLIENT_SECRET')

# Configure GitHub OAuth
github_blueprint = make_github_blueprint(
    client_id='your_client_id',
    client_secret='your_client_secret',
    redirect_to='user_dashboard'  # The endpoint you wish to redirect to
)
app.register_blueprint(github_blueprint, url_prefix="/github")

#github_bp = make_github_blueprint(client_id=git_client_id, client_secret=git_client_secret)
#app.register_blueprint(github_bp, url_prefix='/github_login')

    
# define keys for environmental resources used by the application:
my_secret_url = os.environ['DATABASE_URL']
my_secret_pw = os.environ['PGPASSWORD']
pg_user = os.environ['PGUSER']
pg_host = os.environ['PGHOST']
pg_connection_string = os.environ['PGCONNECTIONSTRING']


# Create a connection pool 
def get_postgres_connection_pool():
    try:
        # Use the connection string directly
        connection_string = os.environ['PGCONNECTIONSTRING']

        # Create a connection pool
        pg_pool = psycopg2.pool.SimpleConnectionPool(1, 10, dsn=connection_string)  # Adjust minconn and maxconn as needed

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
    c.execute('''CREATE TABLE IF NOT EXISTS genailab_users (user_id serial PRIMARY KEY, user_name VARCHAR, user_email VARCHAR, team_id VARCHAR, team_name VARCHAR, userid_created TIMESTAMPTZ, userid_last_login TIMESTAMPTZ);''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS genailab_session_ids (session_id serial PRIMARY KEY, user_id VARCHAR, team_id VARCHAR, session_start_datetime TIMESTAMPTZ, session_end_datetime TIMESTAMPTZ);''')
    
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

@app.before_request
def make_session_permanent():
    session.permanent = True
    if 'chat_log' not in session:
        session['chat_log'] = []
        
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        session['session_id'] = generate_session_id()
        session['user_id'] = request.form.get('user_id')
        session['team_name'] = request.form.get('team_name')
        session['first_name'] = request.form.get('first_name')
        session['email'] = request.form.get('email')
        user = session.get('user_id')
        logging.info(f"User {user} initiated registration.")
        return redirect(url_for('github.login'))
    else:
        return render_template('index.html')
    
@app.route('/register', methods=['POST'])
def register():
    # Store user info from form
    session['user_id'] = request.form['user_id']
    session['team_name'] = request.form['team_name']
    session['first_name'] = request.form['first_name']
    session['email'] = request.form['email']

    # Redirect to GitHub OAuth
    return redirect(url_for('github.login'))


@app.route('/github')
def github_login():
    if not github.authorized:
        return redirect(url_for('github.login'))
    
    resp = github.get('/user')
    assert resp.ok, resp.text
    gh_user_info = resp.json()
    
    return redirect(url_for('user_dashboard'))
    

@app.route('/user_dashboard')
def user_dashboard():
    return render_template('user_dashboard.html')


@app.route('/text_gen', methods=['GET', 'POST'])
def text_gen():
    if request.method == 'POST':
        try:
            user_id = session['user_id']
            session_id = session['session_id']
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
            user_id = session['user_id']
            session_id = session['session_id']
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
            user_id = session['user_id']
            session_id = session['session_id']
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
            user_id = session['user_id']
            session_id = session['session_id']
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
    model_name = request.json.get('model_name')
    session['model_name'] = model_name
    
    user_id = session.get('user_id', 'anonymous')
    session_id = session['session_id']
    
    pg_pool, connection = get_postgres_connection_pool()
    c = connection.cursor()
    c.execute("INSERT INTO models_selected (user_id,session_id, model_name) VALUES (?, ?, ?)", (user_id, session_id, model_name))
    connection.commit()
    pg_pool.putconn(connection)
    return jsonify({"status": "success", "message": f"Model {model_name} selected"})

# Handle evaluation form submissions
@app.route('/submit_evaluation', methods=['POST'])
def submit_evaluation():
    form_data = request.form
    user_id = session.get('user_id', 'anonymous')
    session_id = session['session_id']
    response = form_data.get('response')
    correct = form_data.get('correct')
    score = int(form_data.get('score', 0))
    explanation = form_data.get('explanation')

    pg_pool, connection = get_postgres_connection_pool()
    c = connection.cursor()
    c.execute("INSERT INTO evaluations (user_id, session_id, response, correct, score, explanation) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, session_id, response, correct, score, explanation))
    connection.commit()
    pg_pool.putconn(connection)

    return jsonify({"status": "success", "message": "Evaluation submitted successfully"})

# handle LLM chat messages:
@app.route('/api/handle_message', methods=['POST'])
def handle_message():
    try:
        payload = request.get_json()
        message = payload['message']
        user_message= message
        
        user_id = session.get('user_id')
        logging.info(f"Handling message for user {user_id}: {message}")
        
        session_id = session['session_id']
        
        timestamp_prompt_submitted = datetime.now().isoformat()
        
        model_name = session.get('model_name', 'Unknown Model') 
        
        if model_name == 'Llama3_2_1B':
            ai_response = get_ai_response(message) #get_llama_response(message)
        else:
            ai_response = get_ai_response(message)

        response = ai_response
        #timestamp_aiResponse_received = datetime.now().isoformat()
        timestamp_aiResponse_received = session['timestamp_aiResponse_received']
        
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
        
        pg_pool, connection = get_postgres_connection_pool()
        c = connection.cursor()
        c.execute("INSERT INTO prompts_responses (user_id, session_id, prompt, response, model_name, timestamp_prompt_submitted, timestamp_aiResponse_received) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                (user_id, session_id, user_message, response, model_name, timestamp_prompt_submitted, timestamp_aiResponse_received))
        connection.commit()
        pg_pool.putconn(connection)
        
        logging.info(f"Added chat log record for user {user_id}")
        return jsonify({"response": ai_response})
    except Exception as e:
        logging.error(f"Error in handling message: {str(e)}")
        return jsonify({"response": "Error in processing your message. Please try again."})
    

#get_ai_response(message)
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
    
    pipe = pipeline("text-generation", model="meta-llama/Llama-3.2-1B", token=HF_TOKEN)  
    
    if isinstance(prompts, str):
        prompts = [prompts]  # Convert the single prompt to a list

    responses = []
    system_prompt = "Provide a response to the user."

    for prompt in prompts:
        # Generate response from the LLM
        try:
            # Assuming the model can handle single string inputs as well
            outputs = pipe(f"{system_prompt} {prompt}", max_length=500, num_return_sequences=1)
            response = outputs[0]["generated_text"]
            responses.append(response)
        except Exception as e:
            responses.append(f"Error generating response: {e}")

        return responses if len(responses) > 1 else responses[0]  # Return a single response or a list
    
    

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
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)



    

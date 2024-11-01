from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file # type: ignore
from flask_session import Session # type: ignore
from flask_cors import CORS # type: ignore

import openai, logging, os, socket, csv, json, random # type: ignore
from datetime import datetime, timedelta
from io import BytesIO, StringIO

from flask_dance.contrib.github import make_github_blueprint, github # type: ignore
from authlib.integrations.flask_client import OAuth # type: ignore

import psycopg2 # type: ignore
import psycopg2.extras # type: ignore
import psycopg2.pool # type: ignore

# Load .env file
from dotenv import load_dotenv # type: ignore
load_dotenv()

# Temporary storage for shared data
public_prompts = []
public_responses = []

# Placeholder for prompts storage
team_prompts = []

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

### DATABASE CONNECTION ###
#def check_port(hostname, port):
   # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   # result = sock.connect_ex((hostname, port))
   # sock.close()
   # return result


# Load GitHub client ID and secret from environment variables
app.config["GITHUB_OAUTH_CLIENT_ID"] = os.environ['GITHUB_OAUTH_CLIENT_ID']
app.config["GITHUB_OAUTH_CLIENT_SECRET"] = os.environ['GITHUB_OAUTH_CLIENT_SECRET']

# create github blueprint for authentication:
#github_bp = make_github_blueprint(scope="read:user")
#app.register_blueprint(github_bp, url_prefix="/login")
#github_bp = make_github_blueprint()
#app.register_blueprint(github_bp, url_prefix="/github")

# Register the GitHub OAuth app
'''
github = oauth.register(
    name='github',
    client_id=os.environ['GITHUB_OAUTH_CLIENT_ID'],
    client_secret=os.environ['GITHUB_OAUTH_CLIENT_SECRET'],
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/',
    userinfo_endpoint='https://api.github.com/user',
    client_kwargs={'scope': 'user_id:email'},
)
'''  
    
# define keys for environmental resources used by the application:
my_secret_url = os.environ['DATABASE_URL']
my_secret_pw = os.environ['PGPASSWORD']


# Create a connection pool 
pg_pool = psycopg2.pool.SimpleConnectionPool(0, 112, my_secret_url, sslmode='require')
connection = pg_pool.getconn()


# Mock function to generate a random image URL and caption
def generate_image(prompt):
    image_url = f"https://via.placeholder.com/150?text=Image+for+{prompt}"
    caption = f"This is a caption for the image generated from the prompt: {prompt}"
    return image_url, caption


##### DATABASE / TABLE CREATION AND CALLING FUNCTIONS #####
def create_table_users():
  connection = pg_pool.getconn()
  cursor = connection.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id serial PRIMARY KEY, user_name VARCHAR, user_email VARCHAR, team_id VARCHAR, team_name VARCHAR, userid_created TIMESTAMPTZ, userid_last_login TIMESTAMPTZ);''')
  connection.commit()
  pg_pool.putconn(connection)
  
def get_user_id(user_id):
  connection = pg_pool.getconn()
  cursor = connection.cursor()
  cursor.execute('''SELECT user_id FROM users WHERE user_id= %s;''', (user_id,))
  user_ids = cursor.fetchall()
  pg_pool.putconn(connection)
  return user_id
  
def create_table_session_ids():
  connection = pg_pool.getconn()
  cursor = connection.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS session_ids (session_id serial PRIMARY KEY, user_id VARCHAR, team_id VARCHAR, session_start_datetime TIMESTAMPTZ, session_end_datetime TIMESTAMPTZ);''')
  connection.commit()
  pg_pool.putconn(connection)
  
  
def create_table_team_user_messages():
  connection = pg_pool.getconn()
  cursor = connection.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS team_user_messages (user_id VARCHAR, team_id VARCHAR, session_id VARCHAR, user_team_message VARCHAR, user_team_message_record_date TIMESTAMPTZ);''')
  connection.commit()
  pg_pool.putconn(connection)
  
  
def get_user_team_messages(user_id, session_id):
  connection = pg_pool.getconn()
  cursor = connection.cursor()
  cursor.execute('''SELECT user_team_message FROM team_user_messages WHERE user_id= %s AND session_id = %s;''', (user_id, session_id,))
  user_ids = cursor.fetchall()
  pg_pool.putconn(connection)
  return user_id
  
  
def create_table_team_user_code_files():
  connection = pg_pool.getconn()
  cursor = connection.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS team_user_messages (user_id VARCHAR, team_id VARCHAR, session_id VARCHAR, user_code_file VARCHAR, user_code_file_record_date TIMESTAMPTZ);''')
  connection.commit()
  pg_pool.putconn(connection)
  
def create_table_text_text_prompts_responses():
  connection = pg_pool.getconn()
  cursor = connection.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS text_text_prompts_responses (user_id serial PRIMARY KEY, team_id VARCHAR, session_id VARCHAR, user_prompt VARCHAR, ai_text_response VARCHAR, user_prompt_record_date TIMESTAMPTZ, ai_text_response_record_date TIMESTAMPTZ);''')
  connection.commit()
  pg_pool.putconn(connection)
  
def create_table_text_image_prompts_responses():
  connection = pg_pool.getconn()
  cursor = connection.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS text_image_prompts_responses (user_id serial PRIMARY KEY, team_id VARCHAR, session_id VARCHAR, user_prompt VARCHAR, ai_image_response VARCHAR, user_prompt_record_date TIMESTAMPTZ, ai_image_response_record_date TIMESTAMPTZ);''')
  connection.commit()
  pg_pool.putconn(connection)
  
def create_table_text_video_prompts_responses():
  connection = pg_pool.getconn()
  cursor = connection.cursor()
  cursor.execute('''CREATE TABLE IF NOT EXISTS text_image_prompts_responses (user_id serial PRIMARY KEY, team_id VARCHAR, session_id VARCHAR, user_prompt VARCHAR, ai_video_response VARCHAR, user_prompt_record_date TIMESTAMPTZ, ai_video_response_record_date TIMESTAMPTZ);''')
  connection.commit()
  pg_pool.putconn(connection)


##### CUSTOM FUNCTIONS




###### EXECUTE DATABASE FUNCTIONS ######
create_table_users()

create_table_session_ids()

create_table_team_user_messages()

create_table_team_user_code_files()

create_table_text_text_prompts_responses()

create_table_text_image_prompts_responses()

create_table_text_video_prompts_responses()




###### APPLICATION ROUTING ######


@app.before_request
def make_session_permanent():
    session.permanent = True
    if 'chat_log' not in session:
        session['chat_log'] = []
        
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        user_id = request.form.get('id')
        session['user_id'] = user_id
        timestamp = datetime.now()
        user = session.get('user_id')
       # if not github.authorized:
           # return redirect(url_for("github.login"))
        #resp = github.get("/user")
        #assert resp.ok
        #return f"You are {resp.json()['login']} on GitHub"
        logging.info(f"User {user_id} completed textgen (index page) at: {timestamp}")
        #return f'Hello, {user["login"]}!' if user else 'Hello, please submit your user_id and then log-in using your Github credential!'
        return redirect(url_for('page01'))
    else:
        return render_template('index.html')
    
############ GITUHUB AUTHENTICATION ROUTING ############
@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return github.authorize_redirect(redirect_uri)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/github/callback')
def authorize():
    token = github.authorize_access_token()
    user_id = github.get('user', token=token).json()
    session['user_id'] = user_id
    return redirect(url_for('page01'))

################

@app.route('/page01')
def page01():
    return render_template('page01.html')


@app.route('/api/share/team/prompts', methods=['POST'])
def share_to_team_prompts():
    data = request.get_json()
    message = data.get('message')
    
    if message:
        team_prompts.append(message)
        return jsonify({'success': True}), 200
    return jsonify({'success': False}), 400

@app.route('/team_prompts', methods=['GET'])
def get_team_prompts():
    return jsonify(team_prompts)


@app.route('/team_page', methods=['GET', 'POST'])
def team_page():
    if request.method == 'POST':
        session['user_id'] = user_id
        timestamp = datetime.now()
        logging.info(f"User {user_id} entered team_page at: {timestamp}")
        
        # For simplicity, imagining this is set up to handle AJAX requests
        message = request.form.get('teamMessage')
        if 'team_messages' not in session:
            session['team_messages'] = []
        session['team_messages'].append(message)
        session.modified = True
        return '', 204  # No Content response
    
    elif request.method == 'GET':                                                        # fixme
        user_id = session.get('id')
        session['user_id'] = user_id
        timestamp = datetime.now()
        logging.info(f"User {user_id} posted to team_page at: {timestamp}")
        
        #teamPromptsList = []
        #team_prompts = session.get('team_prompts')
        #teamPromptsList.append(team_prompts)
        #session['teamPromptsList'].append(team_prompts)
        
        #teamLLMResponsesList = []
        #team_llm_responses = session.get('team_llm_responses')
        #teamLLMResponsesList.append(team_llm_responses)
        #session['teamLLMResponsesList'].append(team_llm_responses)
    
    #prompts = session.get('teamPromptsList', [])
    #responses = session.get('teamLLMResponsesList', [])
    messages = session.get('team_messages', [])
    return render_template('team_page.html', messages=messages, team_prompts=team_prompts)

 
@app.route('/text_gen', methods=['GET', 'POST'])
def text_gen():
    if request.method == 'POST':
        try:
            user_id = session['user_id']
            timestamp = datetime.now()
            logging.info(f"User {user_id} started tex_gen at: {timestamp}")
        except Exception as e:
            logging.error(f"Error starting tex_gen_rt: {str(e)}")
            return jsonify({'next': False})
        return jsonify({'next': True})
    else:
        return render_template('text_gen.html')
    


@app.route('/image_gen')
def image_gen():
    return render_template('image_gen.html')  # The modified image generation template


@app.route('/prompts_feed_page')
def prompts_feed_page():
    return render_template('prompts_feed_page.html', prompts=public_prompts)


@app.route('/llm_response_evaluation_page')
def llm_response_evaluation_page():
    return render_template('llm_response_evaluation_page.html', responses=public_responses)

@app.route('/tutorials')
def tutorials():
    return render_template('tutorials.html')

@app.route('/python_basics')
def python_basics():
    return render_template('python_basics.html')

@app.route('/machine_learning')
def machine_learning():
    return render_template('machine_learning.html')


@app.route('/code')
def code():
    return render_template('code.html')

@app.route('/reading')
def reading():
    return render_template('reading.html')

@app.route('/other_resources')
def other_resources():
    return render_template('other_resources.html')

######################## APPLICATION API ENDPOINTS ############################

@app.route('/api/generate_image', methods=['POST'])
def api_generate_image():
    data = request.json
    prompt = data.get('prompt')
    if not prompt:
        return jsonify({'error': 'No prompt provided.'}), 400

    try:
        image_url, caption = generate_image(prompt)
        return jsonify({'image_url': image_url, 'caption': caption})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/share/public/prompts', methods=['POST'])
def share_public_prompts():
    data = request.json
   # message = data.get('message')
    prompt = data.get('prompt')
    #if message:
    if prompt:
        #public_prompts.append(message)
        public_prompts.append(prompt)
        return jsonify({'success': True})
    return jsonify({'success': False}), 400


@app.route('/api/share/public/responses', methods=['POST'])
def share_public_responses():
    data = request.json
    response = data.get('response')
    if response:
        public_responses.append(response)
        return jsonify({'success': True})
    return jsonify({'success': False}), 400


@app.route('/api/handle_message', methods=['POST'])
def handle_message():
    try:
        payload = request.get_json()
        message = payload['message']
        user_id = session.get('user_id')
        logging.info(f"Handling message for user {user_id}: {message}")
        timestamp_prompt_submitted = datetime.now().isoformat()
        ai_response = get_ai_response(message)
        timestamp_aiResponse_received = datetime.now().isoformat()

        # Add record to session chat log
        session['chat_log'].append({
            'user_message': message,
            'ai_response': ai_response,
            'timestamp_prompt_submitted': timestamp_prompt_submitted,
            'timestamp_aiResponse_received': timestamp_aiResponse_received
        })

        logging.info(f"Added chat log record for user {user_id}")
        return jsonify({"response": ai_response})
    except Exception as e:
        logging.error(f"Error in handling message: {str(e)}")
        return jsonify({"response": "Error in processing your message. Please try again."})
    
#fixme:
#@app.route('/api/share/team/prompts', methods=['POST'])
#def share_team_prompts():
   # data = request.get_json()
   # message = data.get('message')
   # team_prompts = []  # fixme           #fixme <-- change to Database solution
    #team_prompts.append(message)
   # session['team_prompts'] = message
    # Perform logic to add the message to the team prompts feed
    # This might involve saving to a database or modifying session data
   # try:
        # Assume some function exists to save the message
        #save_to_team_prompts(message)                              # fixme
       # return jsonify({'team_prompts': team_prompts})
   # except Exception as e:
       # return jsonify({'success': False, 'error': str(e)})

#fixme:
@app.route('/api/share/team/llm_responses', methods=['POST'])
def share_team_llm_responses():
    data = request.get_json()
    message = data.get('message')
    team_llm_responses = []  # fixme           #fixme <-- change to Database solution
    team_llm_responses.append(message)
    session['team_llm_responses'] = message
    # Perform logic to add the message to the team prompts feed
    # This might involve saving to a database or modifying session data
    try:
        # Assume some function exists to save the message
        #save_to_team_prompts(message)                              # fixme
        return jsonify({'team_llm_responses': team_llm_responses})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

#fixme:
@app.route('/api/share/team/team_code', methods=['POST'])
def share_team_team_code():
    data = request.get_json()
    message = data.get('message')
    team_team_code= []  # fixme           #fixme <-- change to Database solution
    team_team_code.append(message)
    session['team_team_code'] = message
    # Perform logic to add the message to the team prompts feed
    # This might involve saving to a database or modifying session data
    try:
        # Assume some function exists to save the message
        #save_to_team_prompts(message)                              # fixme
        return jsonify({'team_team_code': team_code})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})



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
    writer.writerow(['user_message', 'ai_response', 'timestamp_prompt_submitted', 'timestamp_aiResponse_received'])
    for record in chat_log:
        writer.writerow([record['user_message'], record['ai_response'], record['timestamp_prompt_submitted'], record['timestamp_aiResponse_received']])
    output.seek(0)
    return send_file(BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='chat_history.csv')

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
    return response

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)



    

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
@app.route('/callback')
def github_callback():
    # Exchange the authorization code for an access token
    code = request.args.get('code')
    token_url = "https://github.com/login/oauth/access_token"
    # ... Include client_id, client_secret, and code in your POST request to GitHub
    response = requests.post(token_url, data={
        'client_id': os.getenv('GITHUB_OAUTH_CLIENT_ID'),
        'client_secret': os.getenv('GITHUB_OAUTH_CLIENT_SECRET'),
        'code': code
    }, headers={'Accept': 'application/json'})
    # Extract access token from the response
    access_token = response.json().get('access_token')
     #Use the access token to fetch user information if needed
    # ... (e.g. get user info from GitHub API and save it to the session or database)

    # Redirect user to the user dashboard
    return redirect(url_for('user_dashboard'))
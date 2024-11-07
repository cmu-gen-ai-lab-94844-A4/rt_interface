@app.route('/api/handle_message', methods=['POST'])
def handle_message():
    try:
        payload = request.get_json()
        message = payload['message']
        #user_message= message
        
        user_id = session.get('user_id')
        logging.info(f"Handling message for user {user_id}: {message}")
        
        session_id = session['session_id']
        
        timestamp_prompt_submitted = datetime.now().isoformat()
        
        model_name = session.get('model_name') 
        
        if model_name == 'Llama':
            ai_response = get_llama_response(message)
        else:
            ai_response = get_ai_response(message)

        response = ai_response
        timestamp_aiResponse_received = datetime.now().isoformat()
        #timestamp_aiResponse_received = session['timestamp_aiResponse_received']
        
        if model_name == 'Llama':
            # Use the Llama processing
            ai_response = get_llama_response(message)
        else:
            # Default to GPT-4o-mini processing
            ai_response = get_ai_response(message)
        
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
                (user_id, session_id, message, response, model_name, timestamp_prompt_submitted, timestamp_aiResponse_received))
        connection.commit()
        pg_pool.putconn(connection)
        
        logging.info(f"Added chat log record for user {user_id}")
        return jsonify({"response": ai_response})
    except Exception as e:
        logging.error(f"Error in handling message: {str(e)}")
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
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
            response = responses if len(responses) > 1 else responses[0]
        except Exception as e:
            responses.append(f"Error generating response: {e}")

    return responses if len(responses) > 1 else responses[0]  # Return a single response or a list


@app.route('/user_dashboard')       # fixme: add table to database to store challenge selection
def user_dashboard():
    user_id = session.get('user_id')
    session_id = session.get('session_id')
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
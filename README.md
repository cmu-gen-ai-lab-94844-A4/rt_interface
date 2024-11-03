# rt_interface
Heinz GenAI Lab Red Teaming Competition Interface



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

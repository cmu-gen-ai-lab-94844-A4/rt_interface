{% extends 'base.html' %}

{% block content %}
<h1>Team Page</h1>

<!-- Messaging Area -->
<div class="mb-4">
  <h3>Team Messaging Area</h3>
  <form id="messageForm">
    <textarea id="teamMessage" class="form-control mb-2" rows="3" placeholder="Type your message..."></textarea>
    <button type="button" class="btn btn-primary" onclick="sendTeamMessage()">Send Message</button>
  </form>
  <div id="teamMessages" class="overflow-auto" style="height: 200px; margin-top: 10px;">
    <!-- Placeholder for team messages -->
  </div>
</div>

<script>
    function sendTeamMessage() {
        const messageElement = document.getElementById('teamMessage');
        const messageContent = messageElement.value.trim();
        if (!messageContent) return;

        // Clear the input
        messageElement.value = '';

        // Append it to the display area
        const messagesDiv = document.getElementById('teamMessages');
        messagesDiv.innerHTML += `<div class="alert alert-info">${messageContent}</div>`;
    }
</script>

<!-- Feeds -->
<div class="row">
  <!-- Python Code Feed -->
  <div class="col-md-4">
    <h4>Python Code Feed</h4>
    <textarea class="form-control mb-2" rows="3" placeholder="Share Python Code..."></textarea>
    <button class="btn btn-secondary mb-3">Share</button>
    <div class="overflow-auto" style="height: 200px;">
      <!-- Placeholder for shared code -->
    </div>
  </div>

  <!-- Prompts Feed -->
  <div id="promptsFeed">
    <h4>Team Prompts Feed</h4>
    
    <textarea class="form-control" id="team_prompts" name="team_prompts_feed" rows="100" cols="10"> " {{ team_prompts }} " </textarea>
     <button class="btn btn-secondary mb-3"  onclick="getTeamPrompts()">Get Your Team's Shared Prompts</button>
    <div id="team_prompts" class="overflow-auto" style="height: 200px;">
      <!-- Placeholder for shared prompts -->
    </div>
  </div>

  </div>

<script>
    // Fetch and display the team prompts
     // fixme 
     function getTeamPrompts() {
      const message = document.getElementById('team_prompts').value;
      if (!message) return alert('No team prompts to share.');

      fetch('/api/share/team/prompts', {  // Assuming this is your endpoint
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message: message })
      })
      .then(response => response.json())
      .then(data => {
          if (data.success) {
              alert('Shared team prompts to feed!');
          } else {
              alert('Failed to share team prompts to feed.');
          }
      })
      .catch(error => console.error('Error sharing team prompts to feed:', error));
  }
</script>


  <!-- LLM Responses Feed -->
  <div class="col-md-4">
    <h4>LLM Responses</h4>
    <textarea class="form-control mb-2" rows="3" placeholder="Share LLM Response..."></textarea>
    <button class="btn btn-secondary mb-3">Share</button>
    <div id="team_llm_responses" class="overflow-auto" style="height: 200px;">
      <!-- Placeholder for shared LLM responses -->
    </div>
  </div>


</div>

{% endblock %}

</body>
</html>